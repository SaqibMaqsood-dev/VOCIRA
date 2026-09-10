"""
Har qadam alag naapein - waqt kahan ja raha hai?

    STT -> ROUTER -> AUTH -> ERP -> JAWAB(LLM) -> TTS

Har cheez 3 baar chalti hai (pehli baar cold hoti hai).
"""
import asyncio, io, contextlib, json, statistics, time

import numpy as np
import librosa

from backend.microservices.livekit_Rag_services.core.config import settings
from backend.microservices.livekit_Rag_services.services.Speec_to_text_service.sst_whisper import (
    STTWhisper,
)
from backend.microservices.livekit_Rag_services.services.erp_services.auth_client import (
    AuthClient,
)
from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import (
    ERPService,
)
from backend.microservices.livekit_Rag_services.services.groq import human_text, intent_prompt
from backend.microservices.livekit_Rag_services.services.groq.groq import dataConverter
from backend.microservices.livekit_Rag_services.services.rag_engine.query import ask_vocira
from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
    connect_existing_store,
)
from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import (
    split_sentences, tts_converter,
)

noise = io.StringIO()
QUERY = "Have my fees been paid?"
GUARDIAN = "EDU-GRD-2026-00002"
RUNS = 3


async def timed(label, fn, runs=RUNS):
    times, last = [], None
    for _ in range(runs):
        t0 = time.monotonic()
        with contextlib.redirect_stdout(noise):
            last = await fn()
        times.append(time.monotonic() - t0)
    med = statistics.median(times)
    bar = "#" * min(int(med * 8), 46)
    print(f"  {label:<22} {med:6.2f}s  {bar}")
    return med, last


async def main():
    print("=" * 74)
    print(f"LATENCY - '{QUERY}'   ({RUNS} baar, median)")
    print("=" * 74)

    with contextlib.redirect_stdout(noise):
        stt = STTWhisper()
        retr = connect_existing_store()
        erp = ERPService()
        auth = AuthClient(base_url=settings.AUTH_SERVICE_URL)

    # asli audio banayein (ye pipeline ka hissa nahi - user bolta hai)
    a = np.frombuffer(tts_converter(QUERY), dtype=np.int16).astype(np.float32) / 32768.0
    a = librosa.resample(a, orig_sr=22050, target_sr=48000)
    chunk = (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()

    from backend.helper_functions.database.session import SessionLocal
    from backend.microservices.auth_services.models.user_model import Users
    from sqlalchemy import select
    async with SessionLocal() as db:
        uid = (await db.execute(
            select(Users).where(Users.email == "muhmmadahmed763@edu.com")
        )).scalar_one().user_id

    print("\n--- ERP waala raasta ---")
    total = 0.0

    t, _ = await timed("1. STT (Groq)",
                       lambda: asyncio.to_thread(stt.transcribe_bytes, chunk))
    total += t

    t, _ = await timed("2. ROUTER (LLM)",
                       lambda: dataConverter(
                           intent_prompt.ROUTER_PROMPT.format(user_query=QUERY)))
    total += t

    t, _ = await timed("3. AUTH service",
                       lambda: auth.get_internal_user(vocira_user_id=str(uid)))
    total += t

    t, erp_data = await timed("4. ERP fetch",
                              lambda: erp.fetch(resource="fee",
                                                erp_parent_id=GUARDIAN))
    total += t

    t, _ = await timed("5. JAWAB (LLM)",
                       lambda: dataConverter(
                           human_text.build_response_prompt(
                               user_query=QUERY, response=erp_data)))
    total += t

    t, _ = await timed("6. TTS pehla jumla (Piper)",
                       lambda: asyncio.to_thread(
                           tts_converter,
                           split_sentences("Your fees have been paid in full.")[0]))
    total += t

    print(f"\n  {'JAMA':<22} {total:6.2f}s   <- user itni der chup baitha rehta hai")

    print("\n--- RAG waala raasta ---")
    t1, _ = await timed("1. STT (Groq)",
                        lambda: asyncio.to_thread(stt.transcribe_bytes, chunk))
    t2, _ = await timed("2. ROUTER (LLM)",
                        lambda: dataConverter(
                            intent_prompt.ROUTER_PROMPT.format(
                                user_query="What are the school timings?")))
    t3, _ = await timed("3. RAG (embed+search+LLM)",
                        lambda: ask_vocira(retriever=retr,
                                           user_query="What are the school timings?"))
    t4, _ = await timed("4. TTS pehla jumla",
                        lambda: asyncio.to_thread(
                            tts_converter, "The school day runs from eight until two."))
    print(f"\n  {'JAMA':<22} {t1+t2+t3+t4:6.2f}s")

    print("\n" + "=" * 74)


asyncio.run(main())
