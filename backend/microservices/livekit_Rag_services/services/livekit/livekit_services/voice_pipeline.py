import asyncio
import json
import os
import time
import traceback
from uuid import UUID, uuid4

import webrtcvad
from livekit import rtc

from backend.helper_functions.database.session import SessionLocal

from backend.microservices.livekit_Rag_services.core.config import settings
from backend.microservices.livekit_Rag_services.core.rabitmq import RabbitMQ

from backend.microservices.livekit_Rag_services.models.escalation_model import (
    Escalation,
    EscalationStatus,
)
from backend.microservices.livekit_Rag_services.models.message_model import (
    SenderTypeEnum,
)

from backend.microservices.livekit_Rag_services.services.erp_services.auth_client import (
    AuthClient,
)
from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import (
    ERPService,
)

from backend.microservices.livekit_Rag_services.services.groq import (
    answer_cache,
    human_text,
    intent_prompt,
)

from backend.microservices.livekit_Rag_services.services.groq.groq import (
    dataConverter,
    GROQ_FAST_MODEL,
)

from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    INDEX_NAME,
)

from backend.microservices.livekit_Rag_services.services.rag_engine.query import (
    ask_vocira,
)

from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
    connect_existing_store,
)

from backend.microservices.livekit_Rag_services.services.router_services.message_service import (
    MessageService,
)

from backend.microservices.livekit_Rag_services.services.router_services.session_service import (
    SessionService,
)

from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import (
    split_sentences,
    synthesize_with_timing,
)


# =========================================================
# SERVICES
# =========================================================

message_service = MessageService()

auth_client = AuthClient(
    base_url=settings.AUTH_SERVICE_URL
)

erp_service = ERPService()

retriever = connect_existing_store(
    index_name=INDEX_NAME
)

rabbitmq = RabbitMQ()

session_service = SessionService()


# =========================================================
# AUTHORIZATION
# =========================================================

ERP_ALLOWED_ROLES = {
    "parent",
    "guardian",
    "admin",
}

ADMIN_HANDOFF_INTENT = "ADMIN_HANDOFF"


# =========================================================
# HELPER
# =========================================================

def normalize_role(role):
    """
    Normalize role returned from Auth Service.

    Supports:

        "parent"

    and:

        {"name": "parent"}
    """

    if isinstance(role, dict):
        role = role.get("name")

    if role is None:
        return None

    return str(role).strip().lower()


# =========================================================
# READ LIVEKIT USER INFORMATION
# =========================================================

def extract_participant_identity(participant):
    """
    Extract user_id and metadata from LiveKit participant.

    IMPORTANT:
    LiveKit metadata is used only to identify the VOCIRA user.

    It is NOT trusted as the final authorization source.

    Final authorization is performed through Auth Service.
    """

    try:
        metadata = json.loads(
            participant.metadata or "{}"
        )

        if not isinstance(metadata, dict):
            metadata = {}

    except (json.JSONDecodeError, TypeError):
        print(
            f"Invalid metadata from participant "
            f"{participant.identity}: "
            f"{participant.metadata}"
        )

        metadata = {}

    raw_user_id = metadata.get("user_id")

    user_id = None

    if raw_user_id:

        raw_user_id = str(raw_user_id).strip()

        if raw_user_id.lower() not in {
            "",
            "guest",
            "none",
            "null",
            "anonymous",
        }:

            try:

                user_id = UUID(raw_user_id)

            except (ValueError, TypeError):

                print(
                    f"Invalid VOCIRA user_id: "
                    f"{raw_user_id}"
                )

                user_id = None

    return metadata, user_id


# =========================================================
# AGENT STATE -> FRONTEND
#
# LiveKit's own UI components (useVoiceAssistant / BarVisualizer)
# read the agent state from the "lk.agent.state" attribute. We were
# already tracking that state internally (_is_agent_speaking) but
# never publishing it, so the visualizer in the browser had no way
# to tell whether the agent was listening, thinking or speaking.
#
# These are the same values the LiveKit Agents SDK uses.
# =========================================================

AGENT_STATE_ATTRIBUTE = "lk.agent.state"


async def publish_agent_state(service_handle, state: str) -> None:
    """
    Publish the agent's current state: listening / thinking / speaking.

    This is a notification, not real work, so any failure is only
    logged and never interrupts the call.
    """

    room = getattr(service_handle, "room", None)

    if not room or not room.isconnected():
        return

    if getattr(service_handle, "_agent_state", None) == state:
        return

    try:
        await room.local_participant.set_attributes(
            {AGENT_STATE_ATTRIBUTE: state}
        )
        service_handle._agent_state = state

    except Exception as error:
        print(f"[Agent State] '{state}' could not send: {error}")


# The caller's screen shows the conversation as text: what Whisper
# heard them say, and what the agent says back.
TRANSCRIPT_TOPIC = "vocira.transcript"


async def publish_transcript(service_handle, role: str, text: str) -> None:
    """Send a finished line (what Whisper heard the caller say) to the room."""

    room = getattr(service_handle, "room", None)

    if not text or not room or not room.isconnected():
        return

    try:
        await room.local_participant.publish_data(
            json.dumps({"role": role, "text": text}, ensure_ascii=False),
            reliable=True,
            topic=TRANSCRIPT_TOPIC,
        )

    except Exception as error:
        print(f"[Transcript] could not send: {error}")


# The network and the browser's jitter buffer add some delay before a
# frame is heard - small on good wifi, a second or more on a 4G link
# after a reconnect.
PLAYOUT_MARGIN_SECONDS = 0.25


class AgentCaption:
    """
    The words of one agent line, with when each is spoken.

    Each sentence is sent to the page just before its first frame is
    pushed: its words, and when each one starts, counted from the
    moment the line's audio begins. The page starts that clock when it
    actually HEARS the agent's audio begin, and shows every word at its
    own time - so however slow the network is, the text cannot get
    ahead of the voice. (Timing it here, on the server, put the text a
    second early on a 4G link: the server cannot see that delay.)

    The play-out clock is kept here rather than read from the SDK:
    AudioSource.queued_duration goes negative internally after a quiet
    spell and then reports an empty queue for the whole next answer.
    """

    def __init__(self, service_handle, audio_source):
        self._handle = service_handle
        self._id = uuid4().hex[:12]
        self._first_plays_at: float | None = None
        self._plays_until: float | None = None
        self._pending: set[asyncio.Task] = set()

        # Only one line is ever spoken at a time (the TTS lock), and the
        # previous one has been heard to the end - anything left in the
        # source is silence that would hold this line back.
        audio_source.clear_queue()

    def _publish(self, payload: dict) -> None:
        # In order, but without holding up the frames being pushed.
        task = asyncio.create_task(self._send(payload))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _send(self, payload: dict) -> None:
        room = getattr(self._handle, "room", None)

        if not room or not room.isconnected():
            return

        try:
            await room.local_participant.publish_data(
                json.dumps(
                    {"role": "agent", "id": self._id, **payload},
                    ensure_ascii=False,
                ),
                reliable=True,
                topic=TRANSCRIPT_TOPIC,
            )
        except Exception as error:
            print(f"[Transcript] could not send: {error}")

    def add_sentence(self, words, starts, duration: float) -> None:
        now = time.monotonic()

        # Sentences play back to back; one that was not ready in time
        # starts when it is pushed - and the gap is in the timings too.
        plays_at = max(self._plays_until or now, now)
        self._plays_until = plays_at + duration

        if self._first_plays_at is None:
            self._first_plays_at = plays_at

        offset = plays_at - self._first_plays_at

        self._publish(
            {
                "words": list(words),
                "starts": [round(offset + s, 3) for s in starts],
            }
        )

    def _elapsed(self, at: float) -> float:
        return round(max(0.0, at - (self._first_plays_at or at)), 3)

    def finish(self) -> None:
        """Every sentence has been sent; the line ends with its audio."""
        if self._plays_until is not None:
            self._publish({"end": self._elapsed(self._plays_until)})

    def stop(self) -> None:
        """
        Playback was cut off. What was already pushed still plays (up to
        the source's one-second queue); no word after that is shown.
        """
        if self._plays_until is not None:
            cut = min(self._plays_until, time.monotonic() + 1.0)
            self._publish({"end": self._elapsed(cut)})

    async def wait_until_heard(self) -> None:
        """
        The last frame is pushed about a second before it is heard; the
        agent used to switch to "listening" right then, so the mic
        cooldown ran out while its own voice was still playing.
        """
        if self._plays_until is None:
            return

        delay = self._plays_until + PLAYOUT_MARGIN_SECONDS - time.monotonic()

        if delay > 0:
            await asyncio.sleep(min(delay, 30))


# The page's own speech recognition (live captions of the caller) has
# to listen in the same language Whisper does.
CALL_LANGUAGE_ATTRIBUTE = "vocira.language"


async def publish_call_language(service_handle, language: str | None) -> None:
    room = getattr(service_handle, "room", None)

    if not room or not room.isconnected():
        return

    effective = (language or os.getenv("STT_LANGUAGE", "ur")).strip().lower()

    try:
        await room.local_participant.set_attributes(
            {CALL_LANGUAGE_ATTRIBUTE: effective}
        )

    except Exception as error:
        print(f"[Call Language] could not send: {error}")


async def resolve_call_language(user_id) -> str | None:
    """
    The caller's own language choice ("en" / "ur"), or None to use
    the deployment default.

    It decides what Whisper listens for, what the LLM is told to
    answer in, which Piper voice speaks and which greeting opens the
    call - so every one of those reads it from here, and they cannot
    disagree with each other.

    A guest has no account to ask, and an unreachable auth service is
    not a reason to refuse a call: both simply mean "default".
    """

    if not user_id:
        return None

    try:
        caller = await auth_client.get_internal_user(
            vocira_user_id=user_id,
        )
        return caller.get("language")
    except Exception as error:
        print(f"[Language] Could not read the caller's choice: {error}")
        return None


# =========================================================
# AGENT KO BULWAYEIN
# =========================================================

async def speak_text(
    service_handle,
    audio_source,
    text: str,
    language: str | None = None,
) -> bool:
    """
    Have the agent speak a line of text (a greeting, for example).

    Uses the same sentence streaming and locking as a real answer,
    so two voices can never overlap.

    `language` picks the Piper voice - the caller's own choice, so a
    guardian set to Urdu is greeted in an Urdu voice too.
    """

    sentences = split_sentences(text)

    if not sentences:
        return False

    # Track ke tayyar hone ka intezaar
    try:
        await asyncio.wait_for(
            service_handle._track_ready.wait(),
            timeout=10,
        )
    except asyncio.TimeoutError:
        print("[Speak] Agent track is not ready.")
        return False

    async with service_handle._tts_lock:

        if not (
            audio_source
            and service_handle.room
            and service_handle.room.isconnected()
        ):
            print("[Speak] No room or audio source.")
            return False

        sample_rate = 22050
        num_channels = 1
        bytes_per_sample = 2
        samples_per_channel = int(sample_rate * 20 / 1000)
        chunk_size = samples_per_channel * num_channels * bytes_per_sample

        service_handle._is_agent_speaking = True
        await publish_agent_state(service_handle, "speaking")

        caption = AgentCaption(service_handle, audio_source)
        finished = False

        try:
            for sentence in sentences:

                audio_bytes, starts = await asyncio.to_thread(
                    synthesize_with_timing, sentence, language
                )

                if not audio_bytes:
                    continue

                caption.add_sentence(
                    sentence.split(),
                    starts,
                    len(audio_bytes) / bytes_per_sample / sample_rate,
                )

                for i in range(0, len(audio_bytes), chunk_size):

                    if not (
                        service_handle.room
                        and service_handle.room.isconnected()
                    ):
                        return False

                    frame_chunk = audio_bytes[i:i + chunk_size]

                    if len(frame_chunk) < chunk_size:
                        frame_chunk += b"\x00" * (
                            chunk_size - len(frame_chunk)
                        )

                    try:
                        await audio_source.capture_frame(
                            rtc.AudioFrame(
                                data=frame_chunk,
                                sample_rate=sample_rate,
                                num_channels=num_channels,
                                samples_per_channel=samples_per_channel,
                            )
                        )
                    except Exception as frame_error:
                        print(f"[Speak] Frame fail: {frame_error}")
                        return False

            finished = True

        finally:
            if finished:
                caption.finish()
                await caption.wait_until_heard()
            else:
                caption.stop()

            service_handle._is_agent_speaking = False
            service_handle._agent_speech_ended_at = time.monotonic()
            await publish_agent_state(service_handle, "listening")

    print(f"[Speak] bol diya: {text[:60]}")
    return True


# =========================================================
# CONSUME LIVEKIT AUDIO
# =========================================================

async def consume_audio(
    track,
    stt,
    participant,
    service_handle,
    session_id,
    audio_source,
):
    """
    Consume LiveKit participant audio.

    Flow:

        LiveKit Audio
            ↓
        VAD
            ↓
        STT
            ↓
        process_voice_intent()
    """

    # =====================================================
    # 1. PARTICIPANT IDENTITY
    # =====================================================

    metadata, user_id = extract_participant_identity(
        participant
    )

    # -----------------------------------------------------
    # Metadata role is informational only.
    # -----------------------------------------------------

    metadata_role = normalize_role(
        metadata.get("role")
    )

    metadata_type = str(
        metadata.get("type", "guest")
    ).strip().lower()

    # =====================================================
    # 2. LOG IDENTITY
    # =====================================================

    print("=" * 70)

    print(
        f"Participant Identity : "
        f"{participant.identity}"
    )

    print(
        f"VOCIRA User ID       : "
        f"{user_id}"
    )

    print(
        f"Metadata Role        : "
        f"{metadata_role}"
    )

    print(
        f"Metadata Type        : "
        f"{metadata_type}"
    )

    print(
        f"Metadata             : "
        f"{metadata}"
    )

    print(
        "Auth Source          : "
        "Auth Service"
    )

    print("=" * 70)

    # =====================================================
    # 2b. CALLER'S LANGUAGE
    #
    # Read once here, not per utterance: it decides what Whisper
    # listens for, what the LLM is told to answer in and which Piper
    # voice speaks - and those three must agree for the whole call.
    # A guest, or an account that has never chosen, gets None, which
    # every one of those three reads as "use the default".
    # =====================================================

    # A guest has no account to look a preference up in, so theirs
    # rides along in the participant metadata the token was minted
    # with. Everyone else's comes from their account.
    call_language = (
        await resolve_call_language(user_id)
        or (metadata or {}).get("language")
    )

    print(f"Call language        : {call_language or 'default'}")

    await publish_call_language(service_handle, call_language)

    # =====================================================
    # 3. VALIDATE AUDIO TRACK
    # =====================================================

    if not track:

        print(
            "No audio track received."
        )

        return

    try:

        stream = rtc.AudioStream(track)

    except Exception as error:

        print(
            f"Failed to create AudioStream: "
            f"{error}"
        )

        return

    # =====================================================
    # 4. VAD
    # =====================================================

    # Aggressiveness 0-3. At 2, background noise was being counted
    # as "speech" too, which kept starting new generations and left
    # finished answers to go stale and be thrown away. 3 is the
    # strictest filter - it rejects more non-speech.
    vad = webrtcvad.Vad(3)

    audio_buffer = bytearray()

    voice_accumulation = bytearray()

    is_speaking = False

    silence_frames = 0

    # 17 frames x 30ms = ~510ms of silence marks the end of an
    # utterance. This was 25 (750ms) before, which added a quarter
    # second of dead waiting to every question.
    SILENCE_LIMIT = 17

    # Keep ignoring the mic for this long after the agent stops
    # speaking - otherwise the tail of its own audio, coming back
    # through the speaker, becomes the next "question".
    AGENT_COOLDOWN_SECONDS = 0.6

    consecutive_speech_frames = 0

    barge_in_triggered = False

    # -----------------------------------------------------
    # NOISE GATE
    #
    # VAD alone says "speech" for a door closing, a cough, or a fan
    # picking up - one 30ms frame was enough to open an utterance,
    # and whatever followed went to Whisper. Whisper never answers
    # "I heard nothing": it invents a sentence ("Thank you.",
    # "Obrigado.", "موسیقی") and the assistant answered the room.
    #
    # Checking Whisper's own confidence does not help - measured on
    # pure noise it returned "موسیقی" with no_speech_prob 0.0, i.e.
    # completely sure it had heard speech. So the filtering has to
    # happen here, before the audio is ever sent.
    #
    # Real speech holds for a stretch and fills a decent share of
    # the utterance. A knock does neither.
    # -----------------------------------------------------

    # ~240ms of unbroken speech (8 x 30ms).
    MIN_SPEECH_RUN = 8

    # ...and speech has to be at least this much of the whole thing.
    MIN_SPEECH_RATIO = 0.35

    # After a gap this long, the next sound is far more likely to be
    # the room than an actual question - the caller has stopped
    # talking and left the mic open. The bar goes up accordingly.
    LONG_PAUSE_SECONDS = 25.0
    LONG_PAUSE_SPEECH_RUN = 14          # ~420ms
    LONG_PAUSE_SPEECH_RATIO = 0.5

    speech_frames_total = 0
    utterance_frames_total = 0
    longest_speech_run = 0

    last_accepted_at = time.monotonic()

    MAX_ACCUMULATION_BYTES = (
        32000 * 2 * 15
    )

    sample_rate = None

    vad_frame_size = None

    # =====================================================
    # 5. AUDIO LOOP
    # =====================================================

    try:

        async for event in stream:

            # -------------------------------------------------
            # ADMIN HANDOFF CHECK
            # -------------------------------------------------

            if getattr(
                service_handle,
                "_admin_handoff_requested",
                False,
            ):

                print(
                    "[Admin Handoff] "
                    "AI audio processing stopped."
                )

                break

            frame = event.frame

            # -------------------------------------------------
            # AGENT IS SPEAKING -> IGNORE THE MIC ENTIRELY
            #
            # While the agent is still talking, user audio is not
            # processed at all. Barge-in was tried before, but the
            # mic picked up the agent's own voice (and noise) and
            # cut it off mid-sentence - it would say a few words
            # and then fall silent.
            #
            # A short cooldown after speaking too, so the tail of
            # the echo does not become the next question.
            # -------------------------------------------------

            if (
                service_handle._is_agent_speaking
                or (
                    time.monotonic()
                    - getattr(
                        service_handle,
                        "_agent_speech_ended_at",
                        0.0,
                    )
                )
                < AGENT_COOLDOWN_SECONDS
            ):

                audio_buffer.clear()
                voice_accumulation.clear()

                is_speaking = False
                silence_frames = 0
                consecutive_speech_frames = 0
                barge_in_triggered = False

                continue

            # -------------------------------------------------
            # INITIALIZE AUDIO
            # -------------------------------------------------

            if sample_rate is None:

                sample_rate = frame.sample_rate

                vad_frame_size = (
                    int(sample_rate * 30 / 1000)
                    * 2
                    * frame.num_channels
                )

                print(
                    f"Audio initialized: "
                    f"sample_rate={sample_rate}, "
                    f"channels={frame.num_channels}"
                )

            audio_buffer.extend(
                frame.data
            )

            # =================================================
            # PROCESS VAD FRAMES
            # =================================================

            while len(audio_buffer) >= vad_frame_size:

                if getattr(
                    service_handle,
                    "_admin_handoff_requested",
                    False,
                ):

                    print(
                        "[Admin Handoff] "
                        "Stopping VAD processing."
                    )

                    return

                audio_chunk = bytes(
                    audio_buffer[
                        :vad_frame_size
                    ]
                )

                del audio_buffer[
                    :vad_frame_size
                ]

                speech_detected = (
                    await asyncio.to_thread(
                        vad.is_speech,
                        audio_chunk,
                        sample_rate,
                    )
                )

                # =================================================
                # SPEECH
                # =================================================

                if speech_detected:

                    silence_frames = 0

                    consecutive_speech_frames += 1

                    longest_speech_run = max(
                        longest_speech_run,
                        consecutive_speech_frames,
                    )

                    voice_accumulation.extend(
                        audio_chunk
                    )

                    if not is_speaking:

                        is_speaking = True

                        # A fresh utterance - start counting again.
                        speech_frames_total = 0
                        utterance_frames_total = 0
                        longest_speech_run = 1

                        print(
                            f"[Speech Started] "
                            f"{participant.identity}"
                        )

                    speech_frames_total += 1
                    utterance_frames_total += 1

                    # NOTE: barge-in used to live here (the agent
                    # went quiet when the user interrupted). It was
                    # removed because the mic picked up the agent's
                    # own voice and cut it off mid-sentence.
                    #
                    # Audio is now dropped further up while the
                    # agent is speaking, so reaching this point
                    # means the agent is silent.

                # =================================================
                # SILENCE
                # =================================================

                elif is_speaking:

                    silence_frames += 1

                    # Reset the barge-in counter as soon as silence
                    # arrives - otherwise frames from different
                    # moments add up into a false barge-in.
                    consecutive_speech_frames = 0

                    utterance_frames_total += 1

                    voice_accumulation.extend(
                        audio_chunk
                    )

                    if (
                        silence_frames >= SILENCE_LIMIT
                        or len(voice_accumulation)
                        > MAX_ACCUMULATION_BYTES
                    ):

                        captured_audio = bytes(
                            voice_accumulation
                        )

                        print(
                            f"[Speech Finished] "
                            f"Audio bytes: "
                            f"{len(captured_audio)}"
                        )

                        # -----------------------------------------
                        # NOISE GATE
                        # -----------------------------------------

                        quiet_for = (
                            time.monotonic() - last_accepted_at
                        )

                        after_long_pause = (
                            quiet_for >= LONG_PAUSE_SECONDS
                        )

                        required_run = (
                            LONG_PAUSE_SPEECH_RUN
                            if after_long_pause
                            else MIN_SPEECH_RUN
                        )

                        required_ratio = (
                            LONG_PAUSE_SPEECH_RATIO
                            if after_long_pause
                            else MIN_SPEECH_RATIO
                        )

                        speech_ratio = (
                            speech_frames_total / utterance_frames_total
                            if utterance_frames_total
                            else 0.0
                        )

                        if (
                            longest_speech_run < required_run
                            or speech_ratio < required_ratio
                        ):

                            print(
                                f"[Noise Gate] dropped - "
                                f"run={longest_speech_run}"
                                f"/{required_run} "
                                f"ratio={speech_ratio:.2f}"
                                f"/{required_ratio} "
                                f"(quiet for {quiet_for:.0f}s)"
                            )

                            voice_accumulation.clear()
                            silence_frames = 0
                            is_speaking = False
                            consecutive_speech_frames = 0
                            barge_in_triggered = False
                            speech_frames_total = 0
                            utterance_frames_total = 0
                            longest_speech_run = 0

                            continue

                        last_accepted_at = time.monotonic()

                        service_handle._speech_generation += 1

                        generation_id = (
                            service_handle._speech_generation
                        )

                        # -----------------------------------------
                        # CREATE BACKGROUND TASK
                        # -----------------------------------------

                        task = asyncio.create_task(
                            process_voice_intent(
                                chunk=captured_audio,
                                stt=stt,
                                user_id=user_id,
                                user_type=metadata_type,
                                session_id=session_id,
                                audio_source=audio_source,
                                service_handle=service_handle,
                                generation=generation_id,
                                language=call_language,
                            )
                        )

                        service_handle._background_tasks.add(
                            task
                        )

                        task.add_done_callback(
                            service_handle._background_tasks.discard
                        )

                        voice_accumulation.clear()

                        silence_frames = 0

                        is_speaking = False

                        # The next utterance may barge in again
                        consecutive_speech_frames = 0

                        barge_in_triggered = False

    except Exception:

        print(
            "Audio Consumer Error:"
        )

        traceback.print_exc()

    finally:

        try:

            await stream.aclose()

        except Exception as error:

            print(
                f"Failed to close audio stream: "
                f"{error}"
            )


# =========================================================
# VOICE PROCESSING PIPELINE
# =========================================================

async def process_voice_intent(
    chunk: bytes,
    stt,
    user_id,
    user_type,
    session_id,
    audio_source,
    service_handle,
    generation: int,
    language: str | None = None,
):
    """
    Complete voice processing pipeline.

    Flow:

        Audio
          ↓
        STT
          ↓
        Session Validation
          ↓
        Save User Message
          ↓
        Intent Router
          ↓
        ┌─────────────────────────┐
        │ ADMIN_HANDOFF           │
        └─────────────────────────┘
          ↓
        ┌─────────────────────────┐
        │ ERP_QUERY               │
        │                         │
        │ Auth Service            │
        │      ↓                  │
        │ Role Validation         │
        │      ↓                  │
        │ ERP Account Mapping     │
        │      ↓                  │
        │ ERP Service             │
        └─────────────────────────┘
          ↓
        RAG
          ↓
        Save AI Message
          ↓
        TTS
          ↓
        LiveKit
    """

    try:

        ai_response_text = None

        # =====================================================
        # 1. STT
        # =====================================================

        user_query = await asyncio.to_thread(
            stt.transcribe_bytes,
            chunk,
            48000,
            language,
        )

        if not user_query or not user_query.strip():

            return

        user_query = user_query.strip()

        print(
            f"[User]: {user_query}"
        )

        await publish_transcript(service_handle, "user", user_query)

        # A question arrived - "thinking" until the answer is ready.
        await publish_agent_state(service_handle, "thinking")

        # =====================================================
        # 2. HANDOFF CHECK
        # =====================================================

        if getattr(
            service_handle,
            "_admin_handoff_requested",
            False,
        ):

            print(
                "[Admin Handoff] "
                "Ignoring AI processing."
            )

            return

        # =====================================================
        # 3. DATABASE
        # =====================================================

        async with SessionLocal() as db:

            # =================================================
            # SESSION VALIDATION
            # =================================================

            retries = 3

            for attempt in range(retries):

                try:

                    await session_service.get_session_by_id(
                        db=db,
                        user_id=user_id,
                        id_value=session_id,
                    )

                    if attempt > 0:

                        print(
                            f"[Session Check] "
                            f"Session found after retry "
                            f"{attempt}"
                        )

                    break

                except Exception as e:

                    if attempt < retries - 1:

                        print(
                            f"[Session Check Failed] "
                            f"{e} | Retrying..."
                        )

                        await asyncio.sleep(
                            0.2
                        )

                    else:

                        print(
                            f"[Session Check Failed] "
                            f"{e} | Aborting."
                        )

                        return

            # =================================================
            # SAVE USER MESSAGE
            # =================================================

            user_message = (
                await message_service.create_message(
                    db=db,
                    content=user_query,
                    user_id=user_id,
                    usertype=SenderTypeEnum.user.value,
                    session_id=session_id,
                )
            )

            print(
                "[Message Created]"
            )

            print(
                f"   Message ID: "
                f"{user_message.id}"
            )

            # =================================================
            # AN ANSWER WE ALREADY HAVE
            # =================================================

            # Asking the same question twice used to cost the full
            # round trip again - router, ERP, and the LLM call that
            # writes the answer. The cache key includes user_id, so
            # one parent's answer never reaches another.

            cached_answer = answer_cache.get(user_id, user_query, language)

            if cached_answer:

                print(
                    "[Cache] this same question was just asked"
                )

                ai_response_text = cached_answer

            # =================================================
            # INTENT ROUTER
            # =================================================

            # There used to be TWO LLM calls here: one for intent,
            # then another to pick the ERP resource (an 810-line
            # prompt). A single small call now does both jobs.
            #
            # And before that: common questions are unambiguous
            # ("is my fee paid?"), so calling the LLM for them is
            # wasted. ROUTER_PROMPT is ~812 tokens and Groq's limit
            # is on tokens-per-MINUTE - so every router call saved
            # is directly room for one more question. quick_route
            # returns None when it is unsure, and the LLM runs
            # then.
            if cached_answer:

                # The answer already exists - no routing needed.
                # This intent matches no branch, so it falls
                # straight through to the RAG `else` below, where
                # the cached answer is picked up.
                route = {"intent": "CACHED"}

            else:

                route = intent_prompt.quick_route(user_query)

            if route is not None and route.get("intent") != "CACHED":

                print(
                    f"[Router] bina LLM ke: {route}"
                )

            elif route is None:

                router_result = await dataConverter(
                    intent_prompt.ROUTER_PROMPT.format(
                        user_query=user_query
                    ),
                    model=GROQ_FAST_MODEL,
                    max_tokens=80,
                )

                router_raw = (
                    router_result
                    .choices[0]
                    .message
                    .content
                    or ""
                ).strip()

                # markdown fences hata dein
                if router_raw.startswith("```"):
                    _lines = router_raw.splitlines()[1:]
                    if _lines and _lines[-1].strip() == "```":
                        _lines = _lines[:-1]
                    router_raw = "\n".join(_lines).strip()

                try:
                    route = json.loads(router_raw)
                    if not isinstance(route, dict):
                        raise ValueError("route must be an object")
                except Exception:
                    # If the JSON does not parse, fall back to RAG -
                    # that way the user at least gets an answer.
                    print(
                        f"[Router] JSON parse fail: "
                        f"{router_raw!r} — falling back to RAG"
                    )
                    route = {"intent": "RAG"}

            intent = str(
                route.get("intent", "RAG")
            ).strip().upper()

            # "items" is the router's current shape - a list, since a
            # compound question ("Zoya's attendance and has the fee
            # been paid?") needs more than one {resource, student}
            # pair answered in the same turn. quick_route's
            # single-resource fast path (and any older LLM output)
            # still uses the plain "resource"/"student" keys, so that
            # shape is normalised into a one-item list here rather
            # than needing two code paths below.
            erp_items = route.get("items")
            if erp_items is None and route.get("resource"):
                erp_items = [
                    {"resource": route.get("resource"), "student": route.get("student")}
                ]
            erp_items = [
                {
                    "resource": item.get("resource"),
                    "student": (item.get("student") or "").strip() or None,
                }
                for item in (erp_items or [])
                if isinstance(item, dict) and item.get("resource")
            ]

            # Kept for the two spots below that still log a single
            # resource/student pair (the stage-tracking print and the
            # very first item's identity are enough there).
            erp_resource = erp_items[0]["resource"] if erp_items else None
            erp_student = erp_items[0]["student"] if erp_items else None

            print(
                f"[Route]: intent={intent} items={erp_items}"
            )

            # =================================================
            # ADMIN HANDOFF
            # =================================================

            if ADMIN_HANDOFF_INTENT in intent:

                print(
                    "[Route]: ADMIN HANDOFF"
                )

                # -------------------------------------------------
                # CREATE ESCALATION
                #
                # Guests too: a parent asking about admissions has no
                # account yet. Their escalation carries no user_id, and
                # the admin panel labels it "Guest". Nothing private is
                # exposed by this - the staff member simply talks.
                # -------------------------------------------------

                escalation = Escalation(
                    user_id=user_id,
                    message_id=user_message.id,
                    status=EscalationStatus.pending,
                )

                db.add(escalation)

                await db.commit()

                await db.refresh(
                    escalation
                )

                print(
                    "[Escalation Created]"
                )

                print(
                    f"   Escalation ID : "
                    f"{escalation.id}"
                )

                # -------------------------------------------------
                # RABBITMQ
                # -------------------------------------------------

                rabbitmq_payload = {

                    "event": "admin.call.handoff",

                    "call_id": str(
                        session_id
                    ),

                    "session_id": str(
                        session_id
                    ),

                    "room_name":
                        f"room-{session_id}",

                    "caller_id": (
                        str(user_id) if user_id else None
                    ),

                    "escalation_id": str(
                        escalation.id
                    ),

                    "message_id": str(
                        user_message.id
                    ),

                    "message": user_query,
                }

                try:

                    await rabbitmq.publish_admin_handoff(
                        rabbitmq_payload
                    )

                    print(
                        "[RabbitMQ] "
                        "Admin handoff published."
                    )

                except Exception as notification_error:

                    print(
                        "[RabbitMQ] "
                        "Failed to publish admin handoff."
                    )

                    print(
                        notification_error
                    )

                    traceback.print_exc()

                # -------------------------------------------------
                # TELL THE CALLER
                #
                # This has to happen BEFORE request_admin_handoff():
                # that sets _admin_handoff_requested, and after it
                # every handoff check in the TTS path (1456, 1502,
                # 1560) blocks speech. Nothing was said here at
                # all before - the call simply went silent and the
                # caller assumed the system was broken.
                # -------------------------------------------------

                handoff_text = human_text.system_message(
                    "connecting_to_staff",
                    language,
                )

                await message_service.create_message(
                    db=db,
                    content=handoff_text,
                    user_id=user_id,
                    usertype=SenderTypeEnum.ai.value,
                    session_id=session_id,
                    intent="admin_handoff",
                )

                await speak_text(
                    service_handle=service_handle,
                    audio_source=audio_source,
                    text=handoff_text,
                    language=language,
                )

                # -------------------------------------------------
                # LIVEKIT HANDOFF
                # -------------------------------------------------

                await service_handle.request_admin_handoff(
                    user_id=user_id,
                    user_type=user_type,
                    session_id=session_id,
                    user_query=user_query,
                    escalation_id=escalation.id,
                    message_id=user_message.id,
                    language=language,
                )

                return

            # =================================================
            # ERP QUERY
            # =================================================

                        # =================================================
            # ERP QUERY
            # =================================================

            # The router now returns "ERP" (it was "ERP_QUERY").
            # Without a resource, ERP is meaningless - in that case
            # it falls back to RAG so the user is not left empty-handed.
            elif intent == "ERP" and erp_items:

                print(
                    "[Route]: ERP Pipeline"
                )

                # Tells the except block below which part failed.
                # "erp" = could not reach the records, "llm" = the
                # data arrived but no sentence could be built.
                erp_stage = "erp"

                # =================================================
                # SECURITY MODEL
                # =================================================
                #
                # LiveKit metadata is NOT trusted for authorization.
                #
                # LiveKit gives us:
                #
                #     VOCIRA user_id
                #
                # Then:
                #
                #     VOCIRA user_id
                #            ↓
                #       Auth Service
                #            ↓
                #       role + parent_id
                #            ↓
                #       authorization
                #            ↓
                #       ERP Service
                #
                # =================================================

                try:

                    # -------------------------------------------------
                    # 1. USER ID REQUIRED
                    # -------------------------------------------------

                    if not user_id:

                        print(
                            "[ERP Auth] "
                            "No VOCIRA user_id."
                        )

                        ai_response_text = human_text.system_message(
                            "erp_not_authorized",
                            language,
                        )

                    else:

                        print("=" * 70)

                        print(
                            "[ERP AUTHENTICATION]"
                        )

                        print(
                            f"VOCIRA User ID : "
                            f"{user_id}"
                        )

                        print(
                            f"LiveKit Type   : "
                            f"{user_type}"
                        )

                        print(
                            "Auth Source    : "
                            "Auth Service"
                        )

                        print("=" * 70)

                        # =================================================
                        # 2. GET COMPLETE USER FROM AUTH SERVICE
                        # =================================================

                        auth_user = (
                            await auth_client.get_internal_user(
                                vocira_user_id=user_id
                            )
                        )

                        print("=" * 70)

                        print(
                            "[AUTH SERVICE RESPONSE]"
                        )

                        print(
                            f"Requested User ID : "
                            f"{user_id}"
                        )

                        print(
                            f"Auth User         : "
                            f"{auth_user}"
                        )

                        print(
                            f"Response Type     : "
                            f"{type(auth_user)}"
                        )

                        print("=" * 70)

                        # =================================================
                        # 3. VALIDATE AUTH RESPONSE
                        # =================================================

                        if not auth_user:

                            print(
                                "[ERP Auth] "
                                "Auth Service returned no user."
                            )

                            ai_response_text = human_text.system_message(
                                "account_not_verified",
                                language,
                            )

                        elif not isinstance(
                            auth_user,
                            dict,
                        ):

                            print(
                                "[ERP Auth] "
                                "Unexpected Auth Service response."
                            )

                            ai_response_text = human_text.system_message(
                                "account_not_verified",
                                language,
                            )

                        else:

                            # =================================================
                            # 4. VERIFY RETURNED USER ID
                            # =================================================

                            auth_user_id = (
                                auth_user.get("user_id")
                            )

                            if str(auth_user_id) != str(user_id):

                                print(
                                    "[ERP Auth] "
                                    "Auth Service returned a "
                                    "different user_id."
                                )

                                print(
                                    f"Requested : {user_id}"
                                )

                                print(
                                    f"Returned  : {auth_user_id}"
                                )

                                ai_response_text = human_text.system_message(
                                    "account_not_verified",
                                    language,
                                )

                            else:

                                # =================================================
                                # 5. GET AUTH ROLE
                                # =================================================

                                auth_role = normalize_role(
                                    auth_user.get("role")
                                )

                                print("=" * 70)

                                print(
                                    "[AUTHORIZATION CHECK]"
                                )

                                print(
                                    f"VOCIRA User ID : "
                                    f"{user_id}"
                                )

                                print(
                                    f"LiveKit Type   : "
                                    f"{user_type}"
                                )

                                print(
                                    f"Auth Role      : "
                                    f"{auth_role}"
                                )

                                print(
                                    f"Allowed Roles  : "
                                    f"{ERP_ALLOWED_ROLES}"
                                )

                                print(
                                    f"Role Allowed   : "
                                    f"{auth_role in ERP_ALLOWED_ROLES}"
                                )

                                print("=" * 70)

                                # =================================================
                                # 6. ROLE AUTHORIZATION
                                # =================================================

                                if (
                                    auth_role
                                    not in ERP_ALLOWED_ROLES
                                ):

                                    print(
                                        "[ERP Auth] "
                                        "User role is not authorized."
                                    )

                                    ai_response_text = human_text.system_message(
                                        "erp_not_authorized_short",
                                        language,
                                    )

                                else:

                                    print(
                                        "[ERP Auth] "
                                        "User role authorized."
                                    )

                                    # =================================================
                                    # 7. GET ERP PARENT / GUARDIAN ID
                                    # =================================================

                                    erp_parent_id = (
                                        auth_user.get(
                                            "parent_id"
                                        )
                                    )

                                    if not erp_parent_id:

                                        print(
                                            "[ERP Mapping] "
                                            "No parent_id found."
                                        )

                                        print(
                                            f"Auth User Keys: "
                                            f"{list(auth_user.keys())}"
                                        )

                                        ai_response_text = human_text.system_message(
                                            "erp_not_linked",
                                            language,
                                        )

                                    else:

                                        print("=" * 70)

                                        print(
                                            "[ERP ACCOUNT MAPPING]"
                                        )

                                        print(
                                            f"VOCIRA User ID : "
                                            f"{user_id}"
                                        )

                                        print(
                                            f"Auth Role      : "
                                            f"{auth_role}"
                                        )

                                        print(
                                            f"ERP Parent ID  : "
                                            f"{erp_parent_id}"
                                        )

                                        print("=" * 70)

                                        # =================================================
                                        # 8. SEND QUERY TO ERP SERVICE
                                        # =================================================

                                        print(
                                            "[ERP QUERY]"
                                        )

                                        print(
                                            f"User Query     : "
                                            f"{user_query}"
                                        )

                                        print(
                                            f"ERP Parent ID  : "
                                            f"{erp_parent_id}"
                                        )

                                        # The resource(s) already came
                                        # from that same router call -
                                        # no second LLM call needed.
                                        # A compound question ("Zoya's
                                        # attendance and has the fee
                                        # been paid?") has more than
                                        # one item; each is its own
                                        # independent ERP lookup
                                        # (different resource, and
                                        # sometimes a different named
                                        # child), so they run
                                        # concurrently rather than one
                                        # slow round-trip per item.
                                        erp_fetches = [
                                            erp_service.fetch(
                                                resource=item["resource"],
                                                erp_parent_id=erp_parent_id,
                                                student_name=item["student"],
                                                session_id=str(session_id),
                                            )
                                            for item in erp_items
                                        ]
                                        erp_results = await asyncio.gather(
                                            *erp_fetches
                                        )

                                        # Single-item questions (the
                                        # overwhelming majority) keep
                                        # the exact same shape as
                                        # before - a lone dict, not a
                                        # one-element list - so nothing
                                        # about how that dict reads in
                                        # the prompt changes for them.
                                        erp_data = (
                                            erp_results[0]
                                            if len(erp_results) == 1
                                            else list(erp_results)
                                        )

                                        print(
                                            "[ERP DATA]"
                                        )

                                        print(
                                            erp_data
                                        )

                                        # =================================================
                                        # 9. CONVERT ERP DATA TO HUMAN RESPONSE
                                        # =================================================

                                        erp_stage = "llm"

                                        response_prompt = (
                                            human_text.build_response_prompt(
                                                user_query=user_query,
                                                response=erp_data,
                                                language=language,
                                            )
                                        )

                                        converter_response = (
                                            await dataConverter(
                                                prompt=response_prompt,
                                                # The default was 1024. The
                                                # provider RESERVES that many
                                                # tokens and they come out of
                                                # the per-minute budget - while
                                                # the longest ERP answers
                                                # measured were 574 tokens.
                                                # A compound question needs to
                                                # cover more ground in one
                                                # answer, so the budget scales
                                                # with how many topics were
                                                # asked about, capped so one
                                                # oddly long question cannot
                                                # eat the whole per-minute
                                                # token budget by itself.
                                                max_tokens=min(
                                                    640 * len(erp_items), 1600
                                                ),
                                            )
                                        )

                                        ai_response_text = (
                                            converter_response
                                            .choices[0]
                                            .message
                                            .content
                                            .strip()
                                        )

                                        print(
                                            "[ERP AI RESPONSE]"
                                        )

                                        print(
                                            ai_response_text
                                        )

                except Exception as erp_error:

                    # Every failure here used to produce the same
                    # sentence - "unable to retrieve your ERP
                    # information" - which blamed ERP for LLM
                    # problems as well: when the LLM provider
                    # returned 402 for exhausted credits, that is
                    # what the caller heard, even though ERP was
                    # perfectly healthy and the data had arrived.
                    # The two cases are now told apart.

                    stage = erp_stage

                    if stage == "llm":

                        print(
                            "[LLM Error] ERP se data mil gaya tha, "
                            "failed while composing the answer"
                        )

                        ai_response_text = human_text.system_message(
                            "answer_assembly_failed",
                            language,
                        )

                    else:

                        print(
                            "[ERP Error] school records tak "
                            "pahunch nahi saki"
                        )

                        ai_response_text = human_text.system_message(
                            "erp_unreachable",
                            language,
                        )

                    print(
                        f"Error: {type(erp_error).__name__}: {erp_error}"
                    )

                    traceback.print_exc()

            # =================================================
            # RAG QUERY
            # =================================================

            else:

                print(
                    "[Route]: RAG Pipeline"
                )

                # A cache hit lands here - in that case
                # ai_response_text is already filled in and there
                # is no need to run RAG.
                if not cached_answer:

                    ai_response_text = await ask_vocira(
                        retriever=retriever,
                        user_query=user_query,
                        language=language,
                    )

                if ai_response_text:

                    ai_response_text = (
                        ai_response_text.strip()
                    )

            # =================================================
            # HANDOFF CHECK
            # =================================================

            if getattr(
                service_handle,
                "_admin_handoff_requested",
                False,
            ):

                print(
                    "[Admin Handoff] "
                    "Stopping AI response."
                )

                return

            # =================================================
            # EMPTY RESPONSE
            # =================================================

            if not ai_response_text:

                print(
                    "[AI] Empty response."
                )

                return

            print(
                f"[AI]: "
                f"{ai_response_text}"
            )

            # So the same question costs nothing next time.
            # put() rejects error answers on its own.
            if not cached_answer:
                answer_cache.put(
                    user_id=user_id,
                    question=user_query,
                    answer=ai_response_text,
                    language=language,
                )

            # =================================================
            # SAVE AI MESSAGE
            # =================================================

            # What this exchange was about, for the "My Calls" table's
            # Topic column. "attendance:Zoya" packs both the resource
            # and the named child into the one intent field that
            # already existed - no new column needed. A compound
            # question joins each item's "resource:student" with "+"
            # ("attendance:Zoya+fee:Zoya"), which _format_topic() in
            # session_service.py splits back apart. A cached answer
            # carries no resource/student (the router never ran for
            # it), so it falls back to the generic "cached" label.
            if intent == "ERP" and erp_items:
                stored_intent = "+".join(
                    f"{item['resource']}:{item['student']}"
                    if item["student"]
                    else item["resource"]
                    for item in erp_items
                )
            else:
                stored_intent = intent.lower()

            await message_service.create_message(
                db=db,
                content=ai_response_text,
                user_id=user_id,
                usertype=SenderTypeEnum.ai.value,
                session_id=session_id,
                intent=stored_intent,
            )

        # =====================================================
        # 12. FINAL HANDOFF CHECK
        # =====================================================

        if getattr(
            service_handle,
            "_admin_handoff_requested",
            False,
        ):

            print(
                "[TTS] "
                "Admin handoff active."
            )

            return

        # =====================================================
        # 13. TTS
        # =====================================================

        # The audio for the WHOLE answer used to be built here
        # before moving on - 1.5-2 seconds of silence on CPU. Now
        # only the sentence split happens here (which is cheap);
        # each sentence's audio is built just before it plays.
        sentences = split_sentences(ai_response_text)

        if not sentences:

            print(
                "[TTS] "
                "Nothing to speak."
            )

            return

        # =====================================================
        # 14. WAIT FOR LIVEKIT TRACK
        # =====================================================

        try:

            await asyncio.wait_for(
                service_handle._track_ready.wait(),
                timeout=5,
            )

        except asyncio.TimeoutError:

            print(
                "[LiveKit Stream] "
                "Agent track not ready."
            )

            return

        # =====================================================
        # 15. SERIALIZED TTS
        # =====================================================

        async with service_handle._tts_lock:

            if getattr(
                service_handle,
                "_admin_handoff_requested",
                False,
            ):

                print(
                    "[TTS] "
                    "Admin handoff active."
                )

                return

            # -------------------------------------------------
            # DROPPING A STALE ANSWER
            #
            # This used to be `generation != _speech_generation`.
            # The problem: _speech_generation goes up on EVERY
            # utterance, even when the agent is not speaking. If
            # the user said a second sentence (or the mic picked
            # up noise) while the first answer was still being
            # built, the finished answer was thrown away and the
            # user heard NOTHING at all.
            #
            # Now only genuinely stale answers are dropped - ones
            # where a newer answer has already been spoken. Real
            # barge-in (the agent speaking and the user cutting
            # in) is handled in the playback loop below.
            # -------------------------------------------------

            if (
                generation
                <= service_handle._last_played_generation
            ):

                print(
                    "[TTS] "
                    "A newer answer has already been spoken."
                )

                return

            if not (
                audio_source
                and service_handle.room
                and service_handle.room.isconnected()
            ):

                print(
                    "[TTS] "
                    "Audio source or room unavailable."
                )

                return

            # =================================================
            # AUDIO CONFIGURATION
            # =================================================

            sample_rate = 22050

            num_channels = 1

            bytes_per_sample = 2

            samples_per_channel = int(
                sample_rate * 20 / 1000
            )

            chunk_size = (
                samples_per_channel
                * num_channels
                * bytes_per_sample
            )

            service_handle._is_agent_speaking = True
            await publish_agent_state(service_handle, "speaking")

            # Created only once the answer is past the stale check, so
            # a dropped answer never shows up on screen either.
            caption = AgentCaption(service_handle, audio_source)
            stop_playback = False
            finished = False

            # This answer is now being spoken - older ones are
            # rejected automatically from here on.
            service_handle._last_played_generation = generation

            # =================================================
            # PLAY TTS
            # =================================================

            try:

                # The next sentence is prepared WHILE the previous
                # one plays, so there is no gap between sentences.
                next_audio = asyncio.create_task(
                    asyncio.to_thread(
                        synthesize_with_timing,
                        sentences[0],
                        language,
                    )
                )

                for index, sentence in enumerate(sentences):

                    audio_bytes, starts = await next_audio

                    if index + 1 < len(sentences):
                        next_audio = asyncio.create_task(
                            asyncio.to_thread(
                                synthesize_with_timing,
                                sentences[index + 1],
                                language,
                            )
                        )

                    if not audio_bytes:
                        continue

                    print(
                        f"[TTS] jumla {index + 1}/{len(sentences)}"
                    )

                    caption.add_sentence(
                        sentence.split(),
                        starts,
                        len(audio_bytes) / bytes_per_sample / sample_rate,
                    )

                    for i in range(
                        0,
                        len(audio_bytes),
                        chunk_size,
                    ):

                        # -----------------------------------------
                        # HANDOFF
                        # -----------------------------------------

                        if getattr(
                            service_handle,
                            "_admin_handoff_requested",
                            False,
                        ):

                            print(
                                "[TTS] "
                                "Admin handoff requested."
                            )

                            stop_playback = True

                            break

                        # -----------------------------------------
                        # GENERATION
                        # -----------------------------------------

                        # NOTE: a generation check here used to cut
                        # playback off mid-sentence. Audio is no longer
                        # listened to while the agent speaks, so the
                        # generation cannot rise - and the sentence is
                        # spoken in full.

                        # -----------------------------------------
                        # ROOM
                        # -----------------------------------------

                        if not (
                            service_handle.room
                            and service_handle.room.isconnected()
                        ):

                            print(
                                "[TTS] "
                                "Room disconnected."
                            )

                            stop_playback = True

                            break

                        # -----------------------------------------
                        # AUDIO CHUNK
                        # -----------------------------------------

                        frame_chunk = audio_bytes[
                            i:i + chunk_size
                        ]

                        # -----------------------------------------
                        # PAD LAST FRAME
                        # -----------------------------------------

                        if len(frame_chunk) < chunk_size:

                            frame_chunk += (
                                b"\x00"
                                * (
                                    chunk_size
                                    - len(frame_chunk)
                                )
                            )

                        # -----------------------------------------
                        # LIVEKIT FRAME
                        # -----------------------------------------

                        audio_frame = rtc.AudioFrame(
                            data=frame_chunk,
                            sample_rate=sample_rate,
                            num_channels=num_channels,
                            samples_per_channel=(
                                samples_per_channel
                            ),
                        )

                        # -----------------------------------------
                        # SEND FRAME
                        # -----------------------------------------

                        try:

                            await audio_source.capture_frame(
                                audio_frame
                            )

                        except Exception as frame_error:

                            print(
                                f"[TTS] "
                                f"Frame submission failed: "
                                f"{frame_error}"
                            )

                            stop_playback = True

                            break

                    if stop_playback:
                        break

                else:
                    finished = True

            finally:

                if finished:
                    caption.finish()
                    await caption.wait_until_heard()
                else:
                    # Cut off (handoff, dropped room, an error): the
                    # words not yet heard are never shown.
                    caption.stop()

                service_handle._is_agent_speaking = False

                # The cooldown starts here - it stops the tail of
                # the echo from becoming the next question.
                service_handle._agent_speech_ended_at = (
                    time.monotonic()
                )

                await publish_agent_state(service_handle, "listening")

            print(
                "[TTS] "
                "Audio generation completed."
            )

    except Exception:

        print(
            "[Pipeline Error]:"
        )

        traceback.print_exc()