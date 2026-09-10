"""Jawab mein SAARE bachon ka zikr aata hai ya nahi?"""
import asyncio, io, contextlib

from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import ERPService
from backend.microservices.livekit_Rag_services.services.groq import human_text
from backend.microservices.livekit_Rag_services.services.groq.groq import dataConverter

GUARDIAN = "EDU-GRD-2026-00002"
erp = ERPService()
noise = io.StringIO()

CASES = [
    # (sawal, resource, kin naamon ka zikr hona chahiye)
    ("Have my fees been paid?", "fee", ["Muhammad Ali", "Alisha"]),
    ("What is my children's attendance?", "attendance", ["Muhammad Ali", "Alisha"]),
    ("What marks did my children get?", "assessment", ["Alisha"]),
]


async def main():
    print("=" * 74)
    print("JAWAB MUKAMMAL HAI YA NAHI")
    print("=" * 74)

    ok = 0
    for q, resource, must_mention in CASES:
        with contextlib.redirect_stdout(noise):
            data = await erp.fetch(resource=resource, erp_parent_id=GUARDIAN)
            r = await dataConverter(
                human_text.build_response_prompt(user_query=q, response=data)
            )
        answer = (r.choices[0].message.content or "").strip()

        records = data.get("data", [])
        print(f"\nSAWAL : {q}")
        print(f"records: {len(records)}")

        # data mein kaun kaun hai
        who = sorted({
            (rec.get("student_name") or rec.get("customer") or "?")
            for rec in records
        })
        print(f"data mein: {who}")

        missing = [n for n in must_mention
                   if n.split()[0].lower() not in answer.lower()]
        if missing:
            print(f"JAWAB : {answer[:220]}")
            print(f"  FAIL  ghayab: {missing}")
        else:
            print(f"JAWAB : {answer[:220]}")
            print(f"  PASS  sab ka zikr hai")
            ok += 1

    print("\n" + "=" * 74)
    print(f"  {ok}/{len(CASES)} jawab mukammal")
    print("=" * 74)


asyncio.run(main())
