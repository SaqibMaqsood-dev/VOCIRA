"""Phase 2 verification: router, prompt size, TTS streaming."""
import asyncio, io, contextlib, json, time

from backend.microservices.livekit_Rag_services.services.groq import intent_prompt
from backend.microservices.livekit_Rag_services.services.groq.groq import (
    dataConverter, GROQ_FAST_MODEL,
)
from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import ERPService
from backend.microservices.livekit_Rag_services.services.erp_services.prompt import build_erp_prompt
from backend.microservices.livekit_Rag_services.services.text_speech.piper_servies import (
    split_sentences, tts_converter,
)

GUARDIAN = "EDU-GRD-2026-00002"
erp = ERPService()
noise = io.StringIO()

CASES = [
    ("Have the school fees been paid?",        "ERP", "fee"),
    ("How many days was Muhammad Ali present?","ERP", "attendance"),
    ("What marks did Alisha Ahmed get?",       "ERP", "assessment"),
    ("When is the next exam?",                 "ERP", "exam"),
    ("What is tomorrow's class timetable?",    "ERP", "schedule"),
    ("Which class is Muhammad Ali in?",        "ERP", "class"),
    ("What subjects is Muhammad Ali studying?","ERP", "course"),
    ("Show me my children's names",            "ERP", "student"),
    ("What is the admission policy?",          "RAG", None),
    ("What time does the school open?",        "RAG", None),
    ("I want to talk to an admin",             "ADMIN_HANDOFF", None),
]


async def route(q):
    with contextlib.redirect_stdout(noise):
        r = await dataConverter(
            intent_prompt.ROUTER_PROMPT.format(user_query=q),
            model=GROQ_FAST_MODEL, max_tokens=80,
        )
    raw = (r.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        L = raw.splitlines()[1:]
        if L and L[-1].strip() == "```":
            L = L[:-1]
        raw = "\n".join(L).strip()
    return json.loads(raw), r.usage.total_tokens


async def main():
    print("=" * 76)
    print("PHASE 2 VERIFICATION")
    print("=" * 76)

    # ---- 1. prompt sizes ----
    print("\n--- 1. Prompt size ---")
    with contextlib.redirect_stdout(noise):
        r1 = await dataConverter(
            intent_prompt.ROUTER_PROMPT.format(user_query="Have the fees been paid?"),
            model=GROQ_FAST_MODEL, max_tokens=80)
        r2 = await dataConverter(
            build_erp_prompt(user_query="Have the fees been paid?"), max_tokens=80)
    print(f"  naya router prompt : {r1.usage.prompt_tokens} tokens  (ek hi call)")
    print(f"  ERP fallback prompt: {r2.usage.prompt_tokens} tokens  (voice mein use nahi hota)")

    # ---- 2. routing ----
    print("\n--- 2. Router: intent + resource ek call mein ---")
    ok = tot = 0
    for q, exp_intent, exp_res in CASES:
        try:
            rt, tk = await route(q)
        except Exception as e:
            print(f"  FAIL  {q[:42]:44} parse error: {e}")
            continue
        tot += tk
        gi, gr = str(rt.get("intent", "")).upper(), rt.get("resource")
        good = gi == exp_intent and (exp_res is None or gr == exp_res)
        ok += good
        got = gi + (f"/{gr}" if gr else "")
        print(f"  {'PASS' if good else 'FAIL'}  {q[:42]:44} {got}")
    print(f"\n  routing: {ok}/{len(CASES)}   ~{tot // len(CASES)} tokens/call")

    # ---- 3. fetch() ----
    print("\n--- 3. fetch(): resource se seedha data (koi LLM call nahi) ---")
    for res in ["fee", "attendance", "assessment", "exam", "schedule", "class", "course", "student"]:
        t = time.perf_counter()
        try:
            with contextlib.redirect_stdout(noise):
                d = await erp.fetch(resource=res, erp_parent_id=GUARDIAN)
            print(f"  PASS  {res:12} {len(d.get('data', [])):3} records  {(time.perf_counter()-t)*1000:6.0f} ms")
        except Exception as e:
            print(f"  FAIL  {res:12} {type(e).__name__}: {str(e)[:50]}")

    # ---- 4. student filter: naam dekhein, ginti nahi ----
    print("\n--- 4. student_name filter (ginti nahi, ASLI NAAM dekh rahe hain) ---")
    with contextlib.redirect_stdout(noise):
        allr = await erp.fetch(resource="attendance", erp_parent_id=GUARDIAN)
        one  = await erp.fetch(resource="attendance", erp_parent_id=GUARDIAN,
                               student_name="Muhammad Ali")
    names_all = sorted({r.get("student_name") for r in allr.get("data", [])})
    names_one = sorted({r.get("student_name") for r in one.get("data", [])})
    print(f"  bina filter : {names_all}")
    print(f"  filter ke saath: {names_one}")
    good = names_one == ["Muhammad Ali"] and len(names_all) > 1
    print(f"  {'PASS  sirf maanga hua bacha aaya' if good else 'FAIL  filter kaam nahi kar raha'}")

    # ---- 5. TTS: warm-up ke BAAD naapein ----
    print("\n--- 5. TTS sentence streaming ---")
    txt = ("Alisha Ahmed's fees are paid. Muhammad Ali's fees are still overdue. "
           "Five thousand rupees remain outstanding.")
    sents = split_sentences(txt)
    print(f"  {len(sents)} jumlon mein toota:")
    for i, s in enumerate(sents, 1):
        print(f"    {i}. {s}")

    tts_converter("warm up the model")   # cold start ganti mein na aaye

    def avg(fn, n=3):
        ts = []
        for _ in range(n):
            t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
        return sum(ts) / len(ts)

    t_first = avg(lambda: tts_converter(sents[0]))
    t_whole = avg(lambda: tts_converter(txt))
    print(f"\n  pehla jumla : {t_first*1000:6.0f} ms   <- ab itni der baad awaaz shuru")
    print(f"  poora jawab : {t_whole*1000:6.0f} ms   <- pehle itna intezaar hota tha")
    if t_first < t_whole:
        print(f"  PASS  awaaz {t_whole/t_first:.1f}x jaldi shuru hoti hai")
    else:
        print(f"  FAIL  koi behtari nahi")

    print("\n" + "=" * 76)

asyncio.run(main())
