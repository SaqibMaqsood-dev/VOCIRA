"""
Do cheezein:

  1. answer_cache - kya sahi jawab yaad rakhta hai, aur kya doosre
     parent ko LEAK nahi karta (sab se ahem shart)
  2. compact_records - kya maloomat khoye baghair chhota karta hai
"""
import asyncio, io, contextlib, json, time, uuid

from backend.microservices.livekit_Rag_services.services.groq import answer_cache
from backend.microservices.livekit_Rag_services.services.erp_services.compact import (
    compact_records,
)
from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import (
    ERPService,
)

noise = io.StringIO()
p = f = 0


def chk(label, cond, extra=""):
    global p, f
    if cond:
        print(f"  PASS  {label}"); p += 1
    else:
        print(f"  FAIL  {label}  {extra}"); f += 1


async def main():
    print("=" * 76)
    print("CACHE + COMPACT")
    print("=" * 76)

    # =========================================================
    print("\n--- 1. cache: bunyadi ---")
    # =========================================================
    answer_cache.clear()
    u1, u2 = uuid.uuid4(), uuid.uuid4()

    answer_cache.put(u1, "Have my fees been paid?", "Yes, paid in full.")
    chk("yaad rakha", answer_cache.get(u1, "Have my fees been paid?")
        == "Yes, paid in full.")
    chk("chhote-bare harf se farq nahi",
        answer_cache.get(u1, "have my fees been paid") == "Yes, paid in full.")
    chk("sawaliya nishan se farq nahi",
        answer_cache.get(u1, "Have my fees been paid") == "Yes, paid in full.")
    chk("doosra sawal alag hai",
        answer_cache.get(u1, "What is my child's attendance?") is None)

    # =========================================================
    print("\n--- 2. cache: DOOSRE PARENT ko leak to nahi? ---")
    # =========================================================
    chk("doosre user ko wo jawab NAHI milta",
        answer_cache.get(u2, "Have my fees been paid?") is None,
        "<- ye leak hoti to bara masla tha")

    answer_cache.put(u2, "Have my fees been paid?", "You owe five thousand.")
    chk("dono users ka apna apna jawab",
        answer_cache.get(u1, "Have my fees been paid?") == "Yes, paid in full."
        and answer_cache.get(u2, "Have my fees been paid?") == "You owe five thousand.")

    chk("guest (user_id=None) ki apni bucket",
        answer_cache.get(None, "Have my fees been paid?") is None)

    # =========================================================
    print("\n--- 3. cache: ghalti wale jawab yaad NAHI rehte ---")
    # =========================================================
    for bad in [
        "Sorry, I cannot reach the school records system right now.",
        "I found your record, but I am having trouble putting the answer together.",
        "Sorry, the assistant is currently busy. Please try asking again shortly.",
        "Please hold on. I am connecting you to a member of our school staff.",
    ]:
        stored = answer_cache.put(u1, f"q-{bad[:12]}", bad)
        chk(f"rad kiya: {bad[:40]!r}", stored is False)

    # =========================================================
    print("\n--- 4. cache: TTL ---")
    # =========================================================
    real_ttl = answer_cache.TTL_SECONDS
    answer_cache.TTL_SECONDS = 1
    answer_cache.put(u1, "short lived", "abc")
    chk("foran mil raha hai", answer_cache.get(u1, "short lived") == "abc")
    time.sleep(1.2)
    chk("TTL ke baad ghayab", answer_cache.get(u1, "short lived") is None)
    answer_cache.TTL_SECONDS = real_ttl

    # =========================================================
    print("\n--- 5. compact: maloomat khoyi to nahi? ---")
    # =========================================================
    erp = ERPService()
    with contextlib.redirect_stdout(noise):
        data = await erp.fetch(resource="attendance",
                               erp_parent_id="EDU-GRD-2026-00002")

    rows = data["data"]
    chk("har bache ka ek entry", len(rows) == 2, f"mile {len(rows)}")

    for row in rows:
        total = row.get("total_days_recorded")
        counted = sum(v for k, v in row.items() if k.endswith("_days"))
        chk(f"{row['student_name']}: ginti poori ({counted}=={total})",
            counted == total)
        chk(f"{row['student_name']}: ghair-hazri ki tareekhein mojood",
            len(row.get("absent_dates", [])) == row.get("absent_days", 0))
        chk(f"{row['student_name']}: andaroni ID nahi",
            "name" not in row and "student" not in row)

    # kaam nahi aane wala data mile to gir na jaye
    for junk in [{}, {"data": None}, {"data": []}, {"data": "kuch"}]:
        try:
            compact_records("attendance", junk)
            chk(f"kharab input sambhala: {str(junk)[:22]}", True)
        except Exception as e:
            chk(f"kharab input sambhala: {str(junk)[:22]}", False, str(e)[:40])

    print("\n" + "=" * 76)
    print(f"  PASS: {p}   FAIL: {f}")
    print("=" * 76)


asyncio.run(main())
