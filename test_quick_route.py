"""
quick_route() bina LLM ke faisla karta hai. Sawal ye hai:

  1. jab wo faisla karta hai, kya wo faisla SAHI hota hai?
  2. kitne sawal wo bacha leta hai (yaani kitne tokens bache)?

Ghalat routing ki qeemat tokens se kahin zyada hai, is liye har
faisla LLM ke faisle se milaya jata hai.
"""
import asyncio, io, contextlib, json

from backend.microservices.livekit_Rag_services.services.groq import intent_prompt
from backend.microservices.livekit_Rag_services.services.groq.groq import (
    dataConverter, GROQ_FAST_MODEL,
)

noise = io.StringIO()

# (sawal, tawaqqo) - tawaqqo None ka matlab "LLM par chhor do"
CASES = [
    # --- saaf ERP: hamesha zaati ---
    ("What is my child's attendance?",        ("ERP", "attendance")),
    ("Was my son present yesterday?",         ("ERP", "attendance")),
    ("What marks did my child get?",          ("ERP", "assessment")),
    ("Show me the results",                   ("ERP", "assessment")),
    ("Can I see the report card?",            ("ERP", "assessment")),

    # --- ERP sirf "mera" ke sath ---
    ("Have my fees been paid?",               ("ERP", "fee")),
    ("Is my bill outstanding?",               ("ERP", "fee")),
    ("What is my child's timetable?",         ("ERP", "schedule")),
    ("What subjects does my child study?",    ("ERP", "course")),
    ("What are my children's names?",         ("ERP", "student")),

    # --- NAZUK: wahi lafz, magar aam sawal ---
    ("What is the fee structure?",            ("RAG", None)),
    ("What are the school timings?",          ("RAG", None)),
    ("What is the admission policy?",         ("RAG", None)),
    ("What is the uniform policy?",           ("RAG", None)),
    ("What is your name?",                    ("RAG", None)),

    # --- LLM par chhorna chahiye ---
    ("What marks did Alisha get?",            None),   # bache ka naam
    ("I want to talk to an admin",            None),   # handoff
    ("Please connect me to a real person",    None),   # handoff
    ("Wow.",                                  None),   # filler
    ("Tell me about that",                    None),   # mubham
    ("When is the next exam?",                None),   # "mera" nahi
]


async def llm_route(q):
    with contextlib.redirect_stdout(noise):
        r = await dataConverter(
            intent_prompt.ROUTER_PROMPT.format(user_query=q),
            model=GROQ_FAST_MODEL, max_tokens=80,
        )
    try:
        d = json.loads((r.choices[0].message.content or "").strip())
        return d.get("intent"), d.get("resource") or None
    except Exception:
        return "PARSE-FAIL", None


async def main():
    print("=" * 78)
    print("QUICK ROUTE - bina LLM ke faisla")
    print("=" * 78)

    ok = bad = 0
    saved = 0

    for q, want in CASES:
        got = intent_prompt.quick_route(q)
        got_t = (got["intent"], got.get("resource")) if got else None

        if got_t == want:
            mark, ok = "PASS", ok + 1
        else:
            mark, bad = "FAIL", bad + 1

        shown = f"{got_t[0]}/{got_t[1]}" if got_t else "-> LLM"
        print(f"  {mark}  {q:<40} {shown}")

        if got_t != want:
            print(f"        chahiye tha: {want}")

        # jab quick_route faisla kare, LLM se milayein
        if got_t is not None:
            saved += 1
            llm_t = await llm_route(q)
            if llm_t != got_t:
                print(f"        !! LLM alag kehta hai: {llm_t}")
                bad += 1
                ok -= 1

    total = len(CASES)
    print("\n" + "=" * 78)
    print(f"  PASS: {ok}   FAIL: {bad}")
    print(f"  {saved}/{total} sawal bina LLM ke hal ({100*saved//total}%)")
    print(f"  har aise sawal par ~892 tokens bache")
    print("=" * 78)


asyncio.run(main())
