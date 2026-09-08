"""
Kharab halaat mein pipeline atakta to nahi?

Har case ke baad ye dekhna zaroori hai ke _is_agent_speaking wapis
False ho gaya - warna agla sawal sunna hi band ho jata hai
(consume_audio agent ke bolne ke dauran audio girata hai).
"""
import asyncio, uuid, io, contextlib, json

import numpy as np
from sqlalchemy import select

from backend.helper_functions.database.session import SessionLocal
from backend.microservices.livekit_Rag_services.models.escalation_model import Escalation
from backend.microservices.livekit_Rag_services.models.message_model import (
    Message, SenderTypeEnum,
)
from backend.microservices.livekit_Rag_services.models.session_model import (
    Session, SessionStatus,
)
from backend.microservices.livekit_Rag_services.services.livekit.livekit_services import (
    voice_pipeline,
)
from backend.microservices.livekit_Rag_services.services.groq.groq import dataConverter
from backend.microservices.livekit_Rag_services.services.groq import intent_prompt

noise = io.StringIO()
p = f = 0


def chk(label, cond, extra=""):
    global p, f
    if cond:
        print(f"  PASS  {label}  {extra}"); p += 1
    else:
        print(f"  FAIL  {label}  {extra}"); f += 1


class FakeRoom:
    def isconnected(self): return True


class FakeSource:
    def __init__(self): self.frames = 0
    async def capture_frame(self, frame): self.frames += 1


class BoomSource(FakeSource):
    async def capture_frame(self, frame):
        raise RuntimeError("LiveKit track chali gayi")


class FakeHandle:
    def __init__(self):
        self.room = FakeRoom()
        self._track_ready = asyncio.Event(); self._track_ready.set()
        self._tts_lock = asyncio.Lock()
        self._is_agent_speaking = False
        self._agent_speech_ended_at = 0.0
        self._speech_generation = 0
        self._last_played_generation = 0
        self._background_tasks = set()
        self._admin_handoff_requested = False

    async def request_admin_handoff(self, *a, **k):
        self._admin_handoff_requested = True


class DeadSTT:
    def transcribe_bytes(self, *a, **k):
        raise RuntimeError("Groq down")


class EmptySTT:
    def transcribe_bytes(self, *a, **k):
        return ""


async def run_turn(stt, handle, source, uid, sid, chunk):
    handle._speech_generation += 1
    with contextlib.redirect_stdout(noise):
        await voice_pipeline.process_voice_intent(
            chunk=chunk, stt=stt, user_id=uid,
            user_type=SenderTypeEnum.user.value, session_id=sid,
            audio_source=source, service_handle=handle,
            generation=handle._speech_generation,
        )


async def main():
    print("=" * 74)
    print("KHARAB HALAAT")
    print("=" * 74)

    from backend.microservices.auth_services.models.user_model import Users
    async with SessionLocal() as db:
        uid = (await db.execute(
            select(Users).where(Users.email == "muhmmadahmed763@edu.com")
        )).scalar_one().user_id
        sess = Session(id=uuid.uuid4(), user_id=uid, title="error test",
                       status=SessionStatus.active)
        db.add(sess); await db.commit(); sid = sess.id

    silence = np.zeros(48000, dtype=np.int16).tobytes()

    print("\n--- 1. khali transcript ---")
    h, s = FakeHandle(), FakeSource()
    await run_turn(EmptySTT(), h, s, uid, sid, silence)
    chk("chup-chaap wapis aaya", True)
    chk("bolne ka flag saaf hai", h._is_agent_speaking is False)

    print("\n--- 2. STT hi mar gaya ---")
    h, s = FakeHandle(), FakeSource()
    await run_turn(DeadSTT(), h, s, uid, sid, silence)
    chk("crash nahi hua", True)
    chk("bolne ka flag saaf hai", h._is_agent_speaking is False)

    print("\n--- 3. LiveKit track beech mein chali gayi ---")
    from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import (
        tts_converter,
    )
    import librosa
    a = np.frombuffer(tts_converter("What are the school timings?"),
                      dtype=np.int16).astype(np.float32) / 32768.0
    a = librosa.resample(a, orig_sr=22050, target_sr=48000)
    real = (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()

    from backend.microservices.livekit_Rag_services.services.Speec_to_text_service.sst_whisper import (
        STTWhisper,
    )
    with contextlib.redirect_stdout(noise):
        stt = STTWhisper()

    h, s = FakeHandle(), BoomSource()
    await run_turn(stt, h, s, uid, sid, real)
    chk("frame fail par crash nahi", True)
    chk("bolne ka flag saaf hai", h._is_agent_speaking is False,
        "<- warna agla sawal sunayi hi na deta")

    print("\n--- 4. router ab filler ko handoff nahi samajhta ---")
    fillers = ["Wow.", "Okay.", "All right.", "Hmm.", "I see.",
               "I'm going to go.", "Oh really?", "Bye."]
    for q in fillers:
        with contextlib.redirect_stdout(noise):
            r = await dataConverter(
                intent_prompt.ROUTER_PROMPT.format(user_query=q)
            )
        try:
            it = json.loads((r.choices[0].message.content or "").strip())["intent"]
        except Exception:
            it = "PARSE-FAIL"
        chk(f"{q!r:20} -> {it}", it != "ADMIN_HANDOFF")

    print("\n--- 5. asli handoff request ab bhi chalti hai ---")
    for q in ["I want to talk to an admin",
              "Please connect me to a real person",
              "Can I speak to a human being"]:
        with contextlib.redirect_stdout(noise):
            r = await dataConverter(
                intent_prompt.ROUTER_PROMPT.format(user_query=q)
            )
        try:
            it = json.loads((r.choices[0].message.content or "").strip())["intent"]
        except Exception:
            it = "PARSE-FAIL"
        chk(f"{q[:34]!r:38} -> {it}", it == "ADMIN_HANDOFF")

    # safai
    async with SessionLocal() as db:
        await db.execute(Escalation.__table__.delete().where(
            Escalation.message_id.in_(
                select(Message.id).where(Message.session_id == sid))))
        await db.execute(Message.__table__.delete().where(Message.session_id == sid))
        await db.execute(Session.__table__.delete().where(Session.id == sid))
        await db.commit()

    print("\n" + "=" * 74)
    print(f"  PASS: {p}   FAIL: {f}")
    print("=" * 74)


asyncio.run(main())
