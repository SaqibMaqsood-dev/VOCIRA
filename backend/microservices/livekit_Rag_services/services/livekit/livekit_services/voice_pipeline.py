import asyncio
import json
import time
import traceback
from uuid import UUID

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
    tts_converter,
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


# =========================================================
# AGENT KO BULWAYEIN
# =========================================================

async def speak_text(service_handle, audio_source, text: str) -> bool:
    """
    Have the agent speak a line of text (a greeting, for example).

    Uses the same sentence streaming and locking as a real answer,
    so two voices can never overlap.
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

        try:
            for sentence in sentences:

                audio_bytes = await asyncio.to_thread(
                    tts_converter, sentence
                )

                if not audio_bytes:
                    continue

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

        finally:
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

                    voice_accumulation.extend(
                        audio_chunk
                    )

                    if not is_speaking:

                        is_speaking = True

                        print(
                            f"[Speech Started] "
                            f"{participant.identity}"
                        )

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
        )

        if not user_query or not user_query.strip():

            return

        user_query = user_query.strip()

        print(
            f"[User]: {user_query}"
        )

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

            cached_answer = answer_cache.get(user_id, user_query)

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

            erp_resource = route.get("resource")
            erp_student = (route.get("student") or "").strip() or None

            print(
                f"[Route]: intent={intent} "
                f"resource={erp_resource} student={erp_student}"
            )

            # =================================================
            # ADMIN HANDOFF
            # =================================================

            if ADMIN_HANDOFF_INTENT in intent:

                print(
                    "[Route]: ADMIN HANDOFF"
                )

                # -------------------------------------------------
                # SECURITY
                # -------------------------------------------------

                if not user_id:

                    ai_response_text = (
                        "You must be logged in with "
                        "an authorized account to "
                        "contact an admin."
                    )

                    await message_service.create_message(
                        db=db,
                        content=ai_response_text,
                        user_id=user_id,
                        usertype=SenderTypeEnum.ai.value,
                        session_id=session_id,
                    )

                    return

                # -------------------------------------------------
                # CREATE ESCALATION
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

                    "caller_id": str(
                        user_id
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

                handoff_text = (
                    "Please hold on. I am connecting you to "
                    "a member of our school staff."
                )

                await message_service.create_message(
                    db=db,
                    content=handoff_text,
                    user_id=user_id,
                    usertype=SenderTypeEnum.ai.value,
                    session_id=session_id,
                )

                await speak_text(
                    service_handle=service_handle,
                    audio_source=audio_source,
                    text=handoff_text,
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
            elif intent == "ERP" and erp_resource:

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

                        ai_response_text = (
                            "You are not authorized to access "
                            "ERP information. Please log in "
                            "with an authorized account."
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

                            ai_response_text = (
                                "I could not verify your account. "
                                "Please log in again."
                            )

                        elif not isinstance(
                            auth_user,
                            dict,
                        ):

                            print(
                                "[ERP Auth] "
                                "Unexpected Auth Service response."
                            )

                            ai_response_text = (
                                "I could not verify your account. "
                                "Please log in again."
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

                                ai_response_text = (
                                    "I could not verify your account. "
                                    "Please log in again."
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

                                    ai_response_text = (
                                        "You are not authorized "
                                        "to access ERP information."
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

                                        ai_response_text = (
                                            "Your VOCIRA account is not "
                                            "linked to an ERP account."
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

                                        # The resource already came
                                        # from that same router call -
                                        # no second LLM call needed.
                                        erp_data = (
                                            await erp_service.fetch(
                                                resource=erp_resource,
                                                erp_parent_id=erp_parent_id,
                                                student_name=erp_student,
                                            )
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
                                                max_tokens=640,
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

                        ai_response_text = (
                            "I found your record, but I am having "
                            "trouble putting the answer together "
                            "right now. Please ask me again in a moment."
                        )

                    else:

                        print(
                            "[ERP Error] school records tak "
                            "pahunch nahi saki"
                        )

                        ai_response_text = (
                            "Sorry, I cannot reach the school records "
                            "system right now. Please try again shortly."
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
                )

            # =================================================
            # SAVE AI MESSAGE
            # =================================================

            await message_service.create_message(
                db=db,
                content=ai_response_text,
                user_id=user_id,
                usertype=SenderTypeEnum.ai.value,
                session_id=session_id,
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
                        tts_converter,
                        sentences[0],
                    )
                )

                for index, sentence in enumerate(sentences):

                    audio_bytes = await next_audio

                    if index + 1 < len(sentences):
                        next_audio = asyncio.create_task(
                            asyncio.to_thread(
                                tts_converter,
                                sentences[index + 1],
                            )
                        )

                    if not audio_bytes:
                        continue

                    print(
                        f"[TTS] jumla {index + 1}/{len(sentences)}"
                    )

                    stop_playback = False

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

            finally:

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