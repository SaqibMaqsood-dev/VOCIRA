"""
process_user_query() ko seedha chalayein - LiveKit ke baghair.

Asli audio (Piper se banaya hua) andar dalte hain aur dekhte hain
zanjeer kahan tootti hai:

    audio -> STT -> user message save -> ROUTER -> ERP/RAG
          -> ai_response_text -> ai message save -> TTS

Har qadam DB se tasdeeq hota hai, print se nahi.
"""
import asyncio, uuid, time, sys

from sqlalchemy import select

from backend.helper_functions.database.session import SessionLocal
from backend.microservices.livekit_Rag_services.models.message_model import (
    Message, SenderTypeEnum,
)
from backend.microservices.livekit_Rag_services.models.session_model import (
    Session, SessionStatus,
)
from backend.microservices.livekit_Rag_services.services.livekit.livekit_services import (
    voice_pipeline,
)
from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import (
    tts_converter,
)

# muhmmadahmed763@edu.com - guardian EDU-GRD-2026-00002
USER_ID = None          # neeche DB se uthate hain

TURNS = [
    "Have my fees been paid?",          # ERP
    "What is my child's attendance?",   # ERP
    "What are the school timings?",     # RAG
    "Wow.",                             # chhota jumla - yehi live mein atka tha
    "What marks did my child get?",     # Wow. ke BAAD bhi chalna chahiye
    "What is the admission policy?",    # RAG
]


class FakeRoom:
    def isconnected(self):
        return True


class FakeSource:
    def __init__(self):
        self.frames = 0

    async def capture_frame(self, frame):
        self.frames += 1


class FakeHandle:
    """Wahi attributes jo voice_pipeline chhoota hai."""

    def __init__(self):
        self.room = FakeRoom()
        self._track_ready = asyncio.Event()
        self._track_ready.set()
        self._tts_lock = asyncio.Lock()
        self._is_agent_speaking = False
        self._agent_speech_ended_at = 0.0
        self._speech_generation = 0
        self._last_played_generation = 0
        self._background_tasks = set()
        self._admin_handoff_requested = False

    async def request_admin_handoff(self, *a, **k):
        self._admin_handoff_requested = True


async def main():
    print("=" * 78)
    print("POORA PIPELINE - LIVEKIT KE BAGHAIR")
    print("=" * 78)

    # ---- asli user aur session ----
    from backend.microservices.auth_services.models.user_model import Users as User
    async with SessionLocal() as db:
        user = (await db.execute(
            select(User).where(User.email == "muhmmadahmed763@edu.com")
        )).scalar_one_or_none()
        if user is None:
            print("!! muhmmadahmed763@edu.com nahi mila"); sys.exit(1)
        uid = user.user_id

        sess = Session(id=uuid.uuid4(), user_id=uid,
                       title="pipeline e2e", status=SessionStatus.active)
        db.add(sess)
        await db.commit()
        sid = sess.id

    print(f"  user    : {uid}")
    print(f"  session : {sid}\n")

    handle = FakeHandle()
    source = FakeSource()
    stt = voice_pipeline.stt if hasattr(voice_pipeline, "stt") else None
    if stt is None:
        from backend.microservices.livekit_Rag_services.services.Speec_to_text_service.sst_whisper import (
            STTWhisper,
        )
        stt = STTWhisper()

    ok = bad = 0
    for n, phrase in enumerate(TURNS, 1):
        print(f"── baari {n}: {phrase!r} " + "─" * (48 - len(phrase)))

        audio = tts_converter(phrase)            # Piper 22050 Hz
        # pipeline 48 kHz farz karta hai; STT ko wahi rate chahiye
        # jo consume_audio bhejta hai, is liye resample kar dete hain
        import numpy as np, librosa
        a = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        a = librosa.resample(a, orig_sr=22050, target_sr=48000)
        chunk = (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()

        handle._speech_generation += 1
        gen = handle._speech_generation
        before = source.frames
        t0 = time.monotonic()

        await voice_pipeline.process_voice_intent(
            chunk=chunk, stt=stt, user_id=uid,
            user_type=SenderTypeEnum.user.value,
            session_id=sid, audio_source=source,
            service_handle=handle, generation=gen,
        )

        took = time.monotonic() - t0

        async with SessionLocal() as db:
            rows = (await db.execute(
                select(Message).where(Message.session_id == sid)
                .order_by(Message.created_at)
            )).scalars().all()

        heard = [r for r in rows if r.sender_type is SenderTypeEnum.user]
        said  = [r for r in rows if r.sender_type is SenderTypeEnum.ai]

        print(f"  suna    : {heard[-1].content[:60]!r}" if heard else "  suna    : --")
        if len(said) == n:
            print(f"  jawab   : {said[-1].content[:70]!r}")
            print(f"  frames  : {source.frames - before}   waqt: {took:.1f}s")
            print(f"  bolna band hua? {not handle._is_agent_speaking}")
            print("  PASS\n")
            ok += 1
        else:
            print(f"  !! koi AI jawab save nahi hua (ab tak {len(said)}, chahiye {n})")
            print(f"     waqt: {took:.1f}s")
            print("  FAIL\n")
            bad += 1

    # safai
    async with SessionLocal() as db:
        from backend.microservices.livekit_Rag_services.models.escalation_model import (
            Escalation,
        )
        await db.execute(
            # escalations messages ko FK se pakadti hain - pehle wo hatayein
            Escalation.__table__.delete().where(
                Escalation.message_id.in_(
                    select(Message.id).where(Message.session_id == sid)
                )
            )
        )
        await db.execute(Message.__table__.delete().where(Message.session_id == sid))
        await db.execute(Session.__table__.delete().where(Session.id == sid))
        await db.commit()

    print("=" * 78)
    print(f"  PASS: {ok}   FAIL: {bad}")
    print("=" * 78)


asyncio.run(main())
