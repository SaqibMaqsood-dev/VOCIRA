"""
ERP end-to-end test.

Poora chain chalata hai, bilkul waise jaise voice pipeline chalata hai:

    sawal -> LLM query plan -> authorization -> ERP -> LLM jawab
"""
import asyncio
import io
import sys
import contextlib

from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import (
    ERPService,
)
from backend.microservices.livekit_Rag_services.services.groq import human_text
from backend.microservices.livekit_Rag_services.services.groq.groq import (
    dataConverter,
)

GUARDIAN = "EDU-GRD-2026-00002"   # Muhammad Ahmed

QUESTIONS = [
    "What is my child's attendance?",
    "How many days was Muhammad Ali present?",
    "Have the school fees been paid?",
    "Is there any outstanding fee for Muhammad Ali?",
    "What marks did Alisha Ahmed get?",
    "When is the next exam?",
    "What is tomorrow's class timetable?",
    "Which class is Muhammad Ali in?",
    "What subjects is Muhammad Ali studying?",
    "Show me my children's names",
]

erp = ERPService()


async def ask(q):
    """Ek sawal ka poora chain chalayein, shor dabate hue."""
    noise = io.StringIO()
    try:
        with contextlib.redirect_stdout(noise):
            data = await erp.handle_query(
                user_query=q,
                erp_parent_id=GUARDIAN,
            )
    except Exception as e:
        return None, None, f"ERROR: {type(e).__name__}: {e}"

    # kitne records mile
    records = data.get("data") if isinstance(data, dict) else data
    n = len(records) if isinstance(records, list) else "?"

    # LLM se insani jawab banwayein
    try:
        with contextlib.redirect_stdout(noise):
            prompt = human_text.build_response_prompt(
                user_query=q,
                response=data,
            )
            r = await dataConverter(prompt=prompt)
        answer = r.choices[0].message.content.strip()
    except Exception as e:
        answer = f"(jawab banate waqt error: {e})"

    return n, records, answer


async def main():
    print("=" * 78)
    print("ERP END-TO-END TEST   |   Guardian:", GUARDIAN)
    print("=" * 78)

    ok = 0
    for i, q in enumerate(QUESTIONS, 1):
        print(f"\n[{i}] SAWAL: {q}")
        n, records, answer = await ask(q)

        if n is None:
            print(f"    ❌ {answer}")
            continue

        if n == 0:
            print(f"    ⚠️  records: 0  (khali jawab)")
        else:
            ok += 1
            print(f"    ✅ records: {n}")

        # pehla record dikha dein taake data nazar aaye
        if isinstance(records, list) and records:
            first = records[0]
            if isinstance(first, dict):
                preview = ", ".join(
                    f"{k}={v}" for k, v in list(first.items())[:4]
                )
                print(f"    data  : {preview}")

        print(f"    JAWAB : {answer[:260]}")

    print("\n" + "=" * 78)
    print(f"NATEEJA: {ok} / {len(QUESTIONS)} sawalon ka data mila")
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
