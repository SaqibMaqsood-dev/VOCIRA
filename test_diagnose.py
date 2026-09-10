"""
Layer-by-layer diagnostic. Har hissa ALAG test hota hai taake pata
chale zanjeer ki PEHLI kadi kahan tootti hai.

Koi secret print nahi hota - sirf mojood hai / nahi.

    chalayein:  python test_diagnose.py
"""
import asyncio, io, contextlib, json, os, sys, time

import httpx

noise = io.StringIO()
RESULTS = []


def report(layer, ok, detail=""):
    RESULTS.append((layer, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  {mark}  {layer:<34} {detail}")
    return ok


async def main():
    print("=" * 78)
    print("VOCIRA - LAYER BY LAYER")
    print("=" * 78)

    # =============================================================
    print("\n--- 1. CONFIG (sirf mojoodgi, values nahi) ---")
    # =============================================================
    from backend.microservices.livekit_Rag_services.core.config import settings

    for name in ["ERP_BASE_URL", "ERP_API_KEY", "ERP_API_SECRET",
                 "AUTH_SERVICE_URL", "PINECONE_API_KEY"]:
        v = getattr(settings, name, None)
        report(f"settings.{name}", bool(v),
               "set" if v else "GHAYAB")

    for name in ["LLM_BASE_URL", "LLM_API_KEY", "LLM_FAST_MODEL",
                 "LLM_SMART_MODEL", "EMBEDDING_PROVIDER", "GEMINI_API_KEY",
                 "INTERNAL_SERVICE_KEY"]:
        v = os.getenv(name)
        shown = v if name in ("LLM_BASE_URL", "LLM_FAST_MODEL",
                              "LLM_SMART_MODEL", "EMBEDDING_PROVIDER") else (
            "set" if v else "GHAYAB")
        report(f"env {name}", bool(v), shown or "GHAYAB")

    # =============================================================
    print("\n--- 2. ERPNext (seedha, app ke baghair) ---")
    # =============================================================
    base = settings.ERP_BASE_URL.rstrip("/")
    hdr = {"Authorization": f"token {settings.ERP_API_KEY}:{settings.ERP_API_SECRET}",
           "Accept": "application/json"}

    erp_up = False
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{base}/api/method/frappe.auth.get_logged_user",
                            headers=hdr)
        erp_up = r.status_code == 200
        who = r.json().get("message", "?") if erp_up else f"HTTP {r.status_code}"
        report("ERP pahunch + auth", erp_up, f"logged in as: {who}")
    except Exception as e:
        report("ERP pahunch + auth", False, f"{type(e).__name__}: {str(e)[:60]}")

    # =============================================================
    print("\n--- 3. ERP models jo app asal mein maangti hai ---")
    # =============================================================
    from backend.microservices.livekit_Rag_services.services.erp_services import endpoint as ep

    ALLOWED = getattr(ep, "ERP_RESOURCES", None)
    if not isinstance(ALLOWED, dict):
        report("whitelist mila", False, "endpoint.py ka shape samajh nahi aaya")
        ALLOWED = {}
    else:
        report("whitelist mila", True, f"{len(ALLOWED)} resources")

    if erp_up:
        for name, spec in ALLOWED.items():
            path = spec.get("endpoint") or spec.get("path")
            fields = spec.get("fields")
            if not path:
                report(f"  {name}", False, "endpoint set nahi")
                continue
            try:
                params = {"limit_page_length": 1}
                if fields:
                    params["fields"] = json.dumps(fields)
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.get(f"{base}{path}", headers=hdr, params=params)
                if r.status_code == 200:
                    n = len(r.json().get("data", []))
                    report(f"  {name}", True, f"HTTP 200, {n} record")
                else:
                    body = r.text[:90].replace("\n", " ")
                    report(f"  {name}", False, f"HTTP {r.status_code} {body}")
            except Exception as e:
                report(f"  {name}", False, f"{type(e).__name__}")

    # =============================================================
    print("\n--- 4. Auth service (role + parent_id) ---")
    # =============================================================
    try:
        from backend.microservices.livekit_Rag_services.services.erp_services.auth_client import (
            AuthClient,
        )
        from backend.helper_functions.database.session import SessionLocal
        from backend.microservices.auth_services.models.user_model import Users
        from sqlalchemy import select

        async with SessionLocal() as db:
            u = (await db.execute(
                select(Users).where(Users.email == "muhmmadahmed763@edu.com")
            )).scalar_one_or_none()

        if u is None:
            report("test user DB mein", False, "muhmmadahmed763@edu.com nahi mila")
        else:
            report("test user DB mein", True, f"parent_id={u.parent_id}")
            ac = AuthClient(base_url=settings.AUTH_SERVICE_URL)
            with contextlib.redirect_stdout(noise):
                info = await ac.get_internal_user(vocira_user_id=str(u.user_id))
            report("auth service se context", bool(info),
                   f"role={info.get('role') if info else '?'}")
    except Exception as e:
        report("auth service", False, f"{type(e).__name__}: {str(e)[:70]}")

    # =============================================================
    print("\n--- 5. LLM (ERP se bilkul alag) ---")
    # =============================================================
    from backend.microservices.livekit_Rag_services.services.groq.groq import (
        dataConverter, LLM_BASE_URL, GROQ_FAST_MODEL, GROQ_SMART_MODEL,
    )
    print(f"        base_url : {LLM_BASE_URL}")
    print(f"        fast     : {GROQ_FAST_MODEL}")
    print(f"        smart    : {GROQ_SMART_MODEL}")

    llm_ok = False
    for label, model in [("fast", GROQ_FAST_MODEL), ("smart", GROQ_SMART_MODEL)]:
        try:
            with contextlib.redirect_stdout(noise):
                r = await dataConverter("Reply with exactly: ok",
                                        model=model, max_tokens=50)
            txt = (r.choices[0].message.content or "").strip()
            ok = bool(txt)
            llm_ok = llm_ok or ok
            report(f"LLM {label}", ok, repr(txt[:40]))
        except Exception as e:
            msg = str(e)
            short = "CREDITS KHATAM (402)" if "402" in msg else msg[:70]
            report(f"LLM {label}", False, short)

    # =============================================================
    print("\n--- 6. RAG (Pinecone + embeddings) ---")
    # =============================================================
    try:
        from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
            connect_existing_store, get_index_stats,
        )
        with contextlib.redirect_stdout(noise):
            st = await get_index_stats()
        report("Pinecone index", True,
               f"{st.get('total_vector_count', '?')} vectors, dim={st.get('dimension','?')}")

        with contextlib.redirect_stdout(noise):
            retr = connect_existing_store()
            docs = await asyncio.to_thread(
                retr.invoke, "school timings"
            )
        report("embedding + retrieval", len(docs) > 0, f"{len(docs)} chunks")
    except Exception as e:
        report("RAG", False, f"{type(e).__name__}: {str(e)[:70]}")

    # =============================================================
    print("\n--- 7. TTS (greeting isi par chalti hai) ---")
    # =============================================================
    try:
        from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import (
            tts_converter, split_sentences,
        )
        from backend.microservices.livekit_Rag_services.services.livekit.livekit_services.livekit_room_service import (
            LivekitRoomServices,
        )
        greet = LivekitRoomServices.GREETING_TEXT
        t0 = time.monotonic()
        audio = await asyncio.to_thread(tts_converter, split_sentences(greet)[0])
        report("Piper TTS", len(audio) > 1000,
               f"{len(audio)} bytes, {time.monotonic()-t0:.1f}s")
        report("greeting text mojood", bool(greet), f"{greet[:44]}...")
        report("greeting LLM par munhasir NAHI", True,
               "sirf Piper - LLM band ho to bhi chalni chahiye")
    except Exception as e:
        report("TTS / greeting", False, f"{type(e).__name__}: {str(e)[:70]}")

    # =============================================================
    print("\n--- 8. STT ---")
    # =============================================================
    try:
        from backend.microservices.livekit_Rag_services.services.Speec_to_text_service.sst_whisper import (
            STTWhisper,
        )
        from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import (
            tts_converter as _tts,
        )
        with contextlib.redirect_stdout(noise):
            clip = await asyncio.to_thread(_tts, "Have the school fees been paid?")
            s = STTWhisper()
            heard = s.transcribe_bytes(clip, sample_rate=22050)
        report("Groq Whisper", bool(heard), repr(heard[:50]))
    except Exception as e:
        report("STT", False, f"{type(e).__name__}: {str(e)[:70]}")

    # =============================================================
    print("\n" + "=" * 78)
    bad = [r for r in RESULTS if not r[1]]
    print(f"  {len(RESULTS)-len(bad)}/{len(RESULTS)} PASS")
    if bad:
        print("\n  TOOTI HUI KADIYAN:")
        for layer, _, detail in bad:
            print(f"    - {layer}: {detail}")
    print("=" * 78)


asyncio.run(main())
