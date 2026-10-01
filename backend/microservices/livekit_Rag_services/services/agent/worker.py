"""
Vocira's voice agent on the LiveKit Agents framework.

It runs beside the older RabbitMQ worker (livekit_worker.py). A call
comes here when the backend runs with VOICE_ENGINE=agents: the call
token then asks LiveKit to send the agent named "vocira" into the room
(router_services/livekit_services.py), with the call's details - its
session, school, caller and language - as the dispatch metadata.

The framework does the conversation itself - listening (silero VAD),
deciding when the caller has finished (the turn detector for English,
adaptive endpointing for Urdu, which that model does not know),
interruptions, and speaking sentence by sentence - and Vocira's own
logic answers each question (llm_node below).

    uv run --no-sync python -m backend.microservices.livekit_Rag_services.services.agent.run start

(run.py, not this module, is the one to start - see why there.)
"""

import asyncio
import json
import os
import ssl
import sys
import time

# Urdu in the console must never crash a call over a print()
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx  # noqa: E402
import openai  # noqa: E402
from livekit import rtc  # noqa: E402
from livekit.agents.types import FlushSentinel  # noqa: E402
from livekit.agents import (  # noqa: E402
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    metrics,
    room_io,
    stt,
)
from livekit.agents.utils import http_context  # noqa: E402
from livekit.plugins import groq, silero  # noqa: E402
from livekit.plugins.turn_detector.multilingual import MultilingualModel  # noqa: E402

from backend.microservices.livekit_Rag_services.core.config import settings  # noqa: E402
from backend.microservices.livekit_Rag_services.core.rabitmq import MAX_CONCURRENT_CALLS  # noqa: E402
from backend.microservices.livekit_Rag_services.services import tenants  # noqa: E402
from backend.microservices.livekit_Rag_services.services.agent import brain  # noqa: E402
from backend.microservices.livekit_Rag_services.services.agent.brain_loop import (  # noqa: E402
    brain_loop,
    fire_on_brain,
    on_brain,
    stream_from_brain,
)
from backend.microservices.livekit_Rag_services.services.agent import piper_tts  # noqa: E402
from backend.microservices.livekit_Rag_services.services.agent.captions import Captions  # noqa: E402
from backend.microservices.livekit_Rag_services.services.agent.lifecycle import CallLife  # noqa: E402
from backend.microservices.livekit_Rag_services.services.agent.piper_tts import PiperTTS  # noqa: E402
from backend.microservices.livekit_Rag_services.services.groq.groq import GROQ_SMART_MODEL  # noqa: E402
from backend.microservices.livekit_Rag_services.services.livekit.livekit_services import voice_pipeline  # noqa: E402
from backend.microservices.livekit_Rag_services.services.livekit.livekit_services.livekit_room_service import (  # noqa: E402
    LivekitRoomServices,
)
from backend.microservices.livekit_Rag_services.services.rag_engine import query as rag_query  # noqa: E402
from backend.microservices.livekit_Rag_services.services.rag_engine.query import (  # noqa: E402
    search_knowledge_base,
    stream_vocira,
)
from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import (  # noqa: E402
    split_sentences,
)
from backend.microservices.livekit_Rag_services.services.Speec_to_text_service.sst_whisper import (  # noqa: E402
    GROQ_STT_MODEL,
    _is_noise,
)

AGENT_NAME = "vocira"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# explicit dispatch: the call token names this agent (livekit_services.AGENT_NAME)
os.environ.setdefault("LIVEKIT_AGENT_NAME", AGENT_NAME)
DEFAULT_LANGUAGE = os.getenv("STT_LANGUAGE", "ur").strip().lower()

# the turn detector's languages (livekit/turn-detector v0.4.1-intl) - not Urdu
TURN_DETECTOR_LANGUAGES = {"en"}


_brain_warm = False


async def _warm_brain() -> None:
    """
    The first question of the first call paid for all of this - loading the
    embedding model, opening Pinecone and Groq connections - and its search
    took 4.8 s instead of 1.3 s.
    """
    await tenants.refresh(force=True)
    for school in tenants.all_schools().values():
        retriever = await voice_pipeline.retriever_for(school)
        if retriever is not None and school.id == tenants.default_school_id():
            await search_knowledge_base(retriever, "school timings")
    try:
        await rag_query._async_client().models.list()
    except Exception as error:
        print(f"[Agent] could not warm the LLM connection: {error}")


_tls: ssl.SSLContext | None = None


def _share_tls_context() -> None:
    """
    Every call built new TLS contexts - for its Groq client and for the
    framework's HTTP session - and loading the certificates for them stalled
    the call's loop for 1.3-1.4 s just as the greeting was due. A context can
    be shared, so it is built once, here.
    """
    global _tls
    make = getattr(http_context, "_create_ssl_context", None)
    _tls = make() if make is not None else ssl.create_default_context()
    if make is not None:
        http_context._create_ssl_context = lambda: _tls


def _groq_client(api_key: str) -> openai.AsyncClient:
    """One call's connection to Groq (speech-to-text), on the shared TLS context."""
    return openai.AsyncClient(
        api_key=api_key,
        base_url=GROQ_BASE_URL,
        max_retries=0,
        http_client=httpx.AsyncClient(
            verify=_tls or True,
            timeout=httpx.Timeout(connect=15.0, read=5.0, write=5.0, pool=5.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=50, keepalive_expiry=120),
        ),
    )


async def _open_connection(client: openai.AsyncClient) -> None:
    """
    The first question's transcript took ~450 ms longer than the rest: it
    paid for the TLS handshake with Groq. Made while the greeting plays.
    """
    try:
        await client.models.list()
    except Exception as error:
        print(f"[Agent] could not open the Groq connection early: {error}")


def prewarm(proc: JobProcess) -> None:
    """Done before any call: nothing here is paid for by a caller."""
    global _brain_warm
    _share_tls_context()
    # The English turn detector, made for each call, looks its files up with
    # huggingface_hub - imported on the call's loop the first time (340 ms).
    import huggingface_hub.file_download  # noqa: F401
    # The VAD decides when speech has stopped and only then is the audio sent
    # to Whisper: its default 0.55 s of silence was in front of every
    # transcript. 0.3 s - whether the caller has really finished is still the
    # turn detector's and the endpointing's call.
    proc.userdata["vad"] = silero.VAD.load(min_silence_duration=0.3)
    piper_tts.warm_up()
    if not _brain_warm:
        _brain_warm = True
        started = time.monotonic()
        asyncio.run_coroutine_threadsafe(_warm_brain(), brain_loop()).result(timeout=180)
        print(f"[Agent] brain warmed in {time.monotonic() - started:.1f}s")


# Off: a preemptive reply starts before the turn is confirmed and is thrown
# away if the caller goes on - but answering saves the question, may call
# staff, may fill the cache (brain.py), and a half-heard sentence must do
# none of that. It saved only ~150 ms here: the transcript arrives just
# before the turn is confirmed anyway.
_NO_PREEMPTIVE = {"enabled": False}


def turn_handling(language: str) -> dict:
    if language in TURN_DETECTOR_LANGUAGES:
        return {
            "turn_detection": MultilingualModel(),
            "endpointing": {"min_delay": 0.4, "max_delay": 3.0},
            "interruption": {"enabled": True, "min_duration": 0.6},
            "preemptive_generation": _NO_PREEMPTIVE,
        }
    # Urdu: the pause that ends a turn adapts to how this caller speaks
    return {
        "turn_detection": "vad",
        "endpointing": {"mode": "dynamic", "min_delay": 0.45, "max_delay": 2.0},
        "interruption": {"enabled": True, "min_duration": 0.6},
        "preemptive_generation": _NO_PREEMPTIVE,
    }


class VociraAgent(Agent):
    """One call: its school, caller and language, and how its questions are answered."""

    def __init__(self, *, call: brain.Call, room: rtc.Room, life: CallLife, captions: Captions) -> None:
        super().__init__(instructions="")  # Vocira's own prompts are used (brain.py)
        self._call = call
        self._room = room
        self._life = life
        self._captions = captions

    async def on_enter(self) -> None:
        language = self._call.language
        greeting = LivekitRoomServices._GREETINGS.get(language, LivekitRoomServices._GREETINGS["en"])
        self.session.say(greeting.replace("{school}", self._call.school.display_name(language)))

    async def stt_node(self, audio, model_settings):
        """
        Whisper invents speech for noise and stray fragments ("Thank you.",
        "موسیقی") - a test call heard "How can I apply? Thank you." The old
        worker's filter (sst_whisper._is_noise) keeps them out of the question.
        """
        async for event in Agent.default.stt_node(self, audio, model_settings):
            if (
                isinstance(event, stt.SpeechEvent)
                and event.type == stt.SpeechEventType.FINAL_TRANSCRIPT
                and event.alternatives
                and _is_noise(event.alternatives[0].text)
            ):
                print(f"[STT] dropped as noise: {event.alternatives[0].text!r}")
                continue
            yield event

    async def llm_node(self, chat_ctx, tools, model_settings):
        question = ""
        for item in reversed(chat_ctx.items):
            if getattr(item, "role", None) == "user":
                question = (item.text_content or "").strip()
                break
        if not question or self._life.handoff_requested:
            return  # staff were asked for: the AI says nothing more
        print(f"[User]: {question}")
        await self._publish_line("user", question)

        started = time.monotonic()
        reply = await on_brain(brain.reply_to(self._call, question))
        ready = time.monotonic()
        print(f"[Timing:agents] reply_ready={(ready - started) * 1000:.0f}ms")
        if reply is None:
            return
        self._captions.new_reply()
        if reply.handoff:
            self._life.ask_for_staff(reply.handoff)

        # Each piece is spoken as soon as it exists: FlushSentinel ends a
        # speech segment, and its TTS starts at once.
        said: list[str] = []
        finished = False
        try:
            if reply.text is not None:
                for sentence in split_sentences(reply.text):
                    said.append(sentence)
                    yield sentence + " "
                    yield FlushSentinel()
            else:
                async for sentence in stream_from_brain(stream_vocira(reply.prompt)):
                    if not said:
                        print(f"[Timing:agents] first_sentence={(time.monotonic() - ready) * 1000:.0f}ms after reply_ready")
                    said.append(sentence)
                    yield sentence + " "
                    yield FlushSentinel()
                print(f"[Timing:agents] answer_written={(time.monotonic() - started) * 1000:.0f}ms")
            finished = True
        finally:
            # The caller cutting in ends this generator - what was written is
            # still the answer they got, but half an answer is never reused.
            answer = " ".join(said)
            print(f"[AI]{'' if finished else ' (cut off)'}: {answer}")
            if not finished:
                reply.cacheable = False
            fire_on_brain(brain.save_answer(self._call, question, reply, answer))

    async def _publish_line(self, role: str, text: str) -> None:
        """The caller's own words on their screen - the page reads the "vocira.transcript" topic."""
        try:
            await self._room.local_participant.publish_data(
                json.dumps({"role": role, "text": text}, ensure_ascii=False),
                reliable=True,
                topic=voice_pipeline.TRANSCRIPT_TOPIC,
            )
        except Exception as error:
            print(f"[Transcript] could not send: {error}")


server = AgentServer(
    ws_url=settings.LIVEKIT_AGENT_URL,
    api_key=settings.LIVEKIT_API_KEY,
    api_secret=settings.LIVEKIT_API_SECRET,
    setup_fnc=prewarm,
    # loading the VAD and both Piper voices from a cold disk took over the
    # 10 s default, and the first runner was thrown away
    initialize_process_timeout=180.0,
    num_idle_processes=1,
    # Full at MAX_CONCURRENT_CALLS calls, as the older worker was. The
    # default measured the machine's CPU, and with a browser and Docker
    # beside it this machine sat at "full capacity" in the middle of an
    # ordinary call - and a call arriving then got no agent at all.
    load_fnc=lambda srv: len(srv.active_jobs) / MAX_CONCURRENT_CALLS,
    load_threshold=1.0,
    # ERPNext's site is on 8081 - the default here
    port=8091,
)


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    # joined first: linking the session to the caller reads our own identity
    await ctx.connect()
    call = json.loads(ctx.job.metadata or "{}")
    user_id = call.get("user_id")
    school_id = call.get("school")
    await on_brain(tenants.refresh(force=bool(school_id) and not tenants.is_known(school_id)))
    school = tenants.get_school(school_id)
    language = (
        (await on_brain(voice_pipeline.resolve_call_language(user_id)) if user_id else None)
        or call.get("language")
        or DEFAULT_LANGUAGE
    )
    is_user = call.get("type") == "user"
    caller = f"user-{user_id}" if is_user else f"guest-{call.get('session_id')}"
    print(f"[Agent] call {call.get('session_id')} - {school.id}, {language}, {caller}")
    vocira_call = brain.Call(
        session_id=brain.as_uuid(call.get("session_id")),
        user_id=brain.as_uuid(user_id) if is_user else None,
        user_type="user" if is_user else "guest",
        school=school,
        language=language,
    )

    groq_key = settings.returning_groq_api
    groq_client = _groq_client(groq_key)
    ctx.add_shutdown_callback(groq_client.close)
    voice = PiperTTS(language)
    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        stt=groq.STT(model=GROQ_STT_MODEL, language=language, api_key=groq_key, client=groq_client),
        llm=groq.LLM(model=GROQ_SMART_MODEL, api_key=groq_key, client=groq_client),
        tts=voice,
        turn_handling=turn_handling(language),
    )

    life = CallLife(ctx, session, vocira_call, caller)
    captions = Captions(session, ctx.room)
    voice.on_spoken = captions.spoken

    # end of the caller's speech -> first sound of the answer, as heard on the call
    heard = {"user_stopped": None}

    @session.on("user_state_changed")
    def _user_state(ev) -> None:
        if ev.old_state == "speaking" and ev.new_state != "speaking":
            heard["user_stopped"] = time.monotonic()

    @session.on("user_input_transcribed")
    def _transcribed(ev) -> None:
        if ev.is_final:
            print(f"[Heard] transcript: {ev.transcript!r}")

    @session.on("agent_state_changed")
    def _agent_state(ev) -> None:
        if ev.new_state == "speaking" and heard["user_stopped"] is not None:
            waited = time.monotonic() - heard["user_stopped"]
            # longer is not a reply to that speech (one left unanswered while staff were awaited)
            if waited < 15:
                print(f"[Timing:agents] reply_started_after={waited * 1000:.0f}ms")
            heard["user_stopped"] = None

    @session.on("metrics_collected")
    def _metrics(ev: MetricsCollectedEvent) -> None:
        m = ev.metrics
        if isinstance(m, metrics.EOUMetrics):
            print(f"[Timing:agents] end_of_turn={m.end_of_utterance_delay * 1000:.0f}ms "
                  f"transcript_ready={m.transcription_delay * 1000:.0f}ms")
        elif isinstance(m, metrics.TTSMetrics):
            print(f"[Timing:agents] tts_first_audio={m.ttfb * 1000:.0f}ms")

    await session.start(
        agent=VociraAgent(call=vocira_call, room=ctx.room, life=life, captions=captions),
        room=ctx.room,
        # Left unset, LiveKit Cloud's project setting decides whether the
        # call's audio and transcript are uploaded to it. A guardian asking
        # about their child's results is not for a third party's servers -
        # Vocira keeps its own record of each call, in its own database.
        record=False,
        room_options=room_io.RoomOptions(
            participant_identity=caller,
            close_on_disconnect=True,
            # Pacing the framework's own captions to the audio measured the
            # speaking rate on the call's loop - stalls of up to 400 ms, with
            # audio and turn-taking waiting behind them. Vocira's page reads
            # its own captions (the "vocira.transcript" topic), not these.
            text_output=room_io.TextOutputOptions(sync_transcription=False),
        ),
    )
    life.start()
    await ctx.room.local_participant.set_attributes({voice_pipeline.CALL_LANGUAGE_ATTRIBUTE: language})
    await _open_connection(groq_client)  # the greeting is already playing

