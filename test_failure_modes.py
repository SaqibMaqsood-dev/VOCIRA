"""
Jab koi hissa fail ho, user ko SAHI baat pata chalni chahiye - aur
AI ko data GHARNA nahi chahiye.

    ERP fail       -> "school records tak pahunch nahi"
    LLM fail       -> "record mil gaya, jumla nahi bana"   (ERP ko dosh nahi)
    ERP khali      -> "koi record nahi mila"               (invent nahi)
"""
import asyncio, uuid, io, contextlib, types

import numpy as np
import librosa
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
from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import (
    tts_converter,
)
from backend.microservices.livekit_Rag_services.services.Speec_to_text_service.sst_whisper import (
    STTWhisper,
)

noise = io.StringIO()
p = f = 0


def chk(label, cond, extra=""):
    global p, f
    if cond:
        print(f"  PASS  {label}"); p += 1
    else:
        print(f"  FAIL  {label}  {extra}"); f += 1


class FakeRoom:
    def isconnected(self): return True


class FakeSource:
    def __init__(self): self.frames = 0
    async def capture_frame(self, frame): self.frames += 1


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


def make_chunk(phrase):
    a = np.frombuffer(tts_converter(phrase), dtype=np.int16)
    a = a.astype(np.float32) / 32768.0
    a = librosa.resample(a, orig_sr=22050, target_sr=48000)
    return (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()


async def last_ai(sid):
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(Message).where(Message.session_id == sid)
            .order_by(Message.created_at)
        )).scalars().all()
    ai = [r for r in rows if r.sender_type is SenderTypeEnum.ai]
    return ai[-1].content if ai else ""


async def main():
    print("=" * 78)
    print("FAILURE MODES")
    print("=" * 78)

    from backend.microservices.auth_services.models.user_model import Users
    async with SessionLocal() as db:
        uid = (await db.execute(
            select(Users).where(Users.email == "ahmed@test.com")
        )).scalar_one().user_id
        s = Session(id=uuid.uuid4(), user_id=uid, title="failure modes",
                    status=SessionStatus.active)
        db.add(s); await db.commit(); sid = s.id

    with contextlib.redirect_stdout(noise):
        stt = STTWhisper()
    chunk = make_chunk("Have my fees been paid?")

    real_fetch = voice_pipeline.erp_service.fetch
    real_conv = voice_pipeline.dataConverter

    async def run():
        h, src = FakeHandle(), FakeSource()
        h._speech_generation += 1
        with contextlib.redirect_stdout(noise):
            await voice_pipeline.process_voice_intent(
                chunk=chunk, stt=stt, user_id=uid,
                user_type=SenderTypeEnum.user.value, session_id=sid,
                audio_source=src, service_handle=h,
                generation=h._speech_generation,
            )
        return h, src

    # ---------------------------------------------------------
    print("\n--- 1. ERP bilkul down ---")
    # ---------------------------------------------------------
    async def dead_fetch(*a, **k):
        raise ConnectionError("ERPNext se rabta nahi")

    voice_pipeline.erp_service.fetch = dead_fetch
    h, src = await run()
    voice_pipeline.erp_service.fetch = real_fetch

    ans = await last_ai(sid)
    print(f"        jawab: {ans[:88]!r}")
    chk("user ko batata hai records nahi mile",
        "cannot reach" in ans.lower() or "records" in ans.lower(), ans[:60])
    chk("data GHARA nahi (koi raqam/naam nahi)",
        not any(w in ans.lower() for w in ["rupees", "alisha", "muhammad", "paid"]),
        ans[:60])
    chk("audio phir bhi baja", src.frames > 0, f"frames={src.frames}")
    chk("bolne ka flag saaf", h._is_agent_speaking is False)

    # ---------------------------------------------------------
    print("\n--- 2. ERP theek, LLM fail (jumla banate waqt) ---")
    # ---------------------------------------------------------
    # NOTE: pehle yahan "pehli call router hai" farz kiya gaya tha.
    # quick_route aane ke baad ye ghalat ho gaya - aam sawal bina
    # LLM ke rout hote hain, to pehli call HI jumla banane wali
    # hoti hai. Ab prompt dekh kar tay karte hain: jis mein ERP
    # data ho (AVAILABLE INFORMATION) wahi fail karayein.
    async def flaky_conv(*a, **k):
        prompt = k.get("prompt") or (a[0] if a else "")
        if "AVAILABLE INFORMATION" in str(prompt):
            raise RuntimeError("402 credits khatam")   # jumla banana - fail
        return await real_conv(*a, **k)                # router - chalne dein

    voice_pipeline.dataConverter = flaky_conv
    h, src = await run()
    voice_pipeline.dataConverter = real_conv

    ans = await last_ai(sid)
    print(f"        jawab: {ans[:88]!r}")
    chk("LLM ka masla ERP ke khate mein NAHI dala",
        "cannot reach the school records" not in ans.lower(), ans[:60])
    chk("kehta hai record mil gaya tha",
        "found your record" in ans.lower(), ans[:60])
    chk("audio phir bhi baja", src.frames > 0, f"frames={src.frames}")

    # ---------------------------------------------------------
    print("\n--- 3. ERP chal raha hai magar record khali ---")
    # ---------------------------------------------------------
    async def empty_fetch(*a, **k):
        return {"success": True, "resource": "fee", "count": 0, "data": []}

    voice_pipeline.erp_service.fetch = empty_fetch
    h, src = await run()
    voice_pipeline.erp_service.fetch = real_fetch

    ans = await last_ai(sid)
    # LLM Unicode apostrophe (U+2019) use karta hai - normalize karein
    flat = ans.lower().replace("’", "'")
    print(f"        jawab: {ans[:88]!r}")
    chk("koi jhoota record nahi ghara",
        not any(w in ans.lower() for w in
                ["rupees", "acc-sinv", "alisha", "muhammad ali"]), ans[:70])
    chk("saaf kehta hai record nahi mila",
        any(w in flat for w in
            ["no ", "not ", "don't", "do not", "unable", "couldn't"]), ans[:70])

    # ---------------------------------------------------------
    print("\n--- 4. fix ke baad asli ERP dobara ---")
    # ---------------------------------------------------------
    h, src = await run()
    ans = await last_ai(sid)
    print(f"        jawab: {ans[:88]!r}")
    chk("asli ERP data wapis aa raha hai",
        any(w in ans.lower() for w in ["alisha", "muhammad", "fee"]), ans[:70])
    chk("audio baja", src.frames > 0, f"frames={src.frames}")

    # safai
    async with SessionLocal() as db:
        await db.execute(Escalation.__table__.delete().where(
            Escalation.message_id.in_(
                select(Message.id).where(Message.session_id == sid))))
        await db.execute(Message.__table__.delete().where(Message.session_id == sid))
        await db.execute(Session.__table__.delete().where(Session.id == sid))
        await db.commit()

    print("\n" + "=" * 78)
    print(f"  PASS: {p}   FAIL: {f}")
    print("=" * 78)


asyncio.run(main())
