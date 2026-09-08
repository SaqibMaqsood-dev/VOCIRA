"""
Support ticket ka poora raasta - frontend jaisa, gateway se guzar kar.

Do soortein alag alag jaanchi jati hain:

    GUEST  (login nahi)  ->  email lazmi
    LOGIN  (token ke sath) ->  email account se, request ka email
                               nazarandaz

Ticket waqai ERPNext mein bana ya nahi, ye ERPNext se SEEDHA poocha
jata hai - apni hi API ke jawab par bharosa nahi kiya jata.
"""

import httpx

from backend.microservices.livekit_Rag_services.core.config import settings

GATEWAY = "http://localhost:9000"
ERP = settings.ERP_BASE_URL.rstrip("/")
ERP_HEADERS = {
    "Authorization": (
        f"token {settings.ERP_API_KEY}:{settings.ERP_API_SECRET}"
    ),
    "Accept": "application/json",
}

EMAIL = "muhmmadahmed763@edu.com"
PASSWORD = "Test@1234"
GUEST_EMAIL = "walid.guest@example.com"

SUBJECT = "Voice call disconnects after greeting"
MESSAGE = "Mic dabane ke baad greeting aati hai phir call kat jati hai."

p = f = 0
made = []


def chk(label, cond, extra=""):
    global p, f
    if cond:
        print(f"  PASS  {label}  {extra}")
        p += 1
    else:
        print(f"  FAIL  {label}  {extra}")
        f += 1


def erp_get(path):
    r = httpx.get(f"{ERP}{path}", headers=ERP_HEADERS, timeout=30)
    return r.status_code, (r.json() if r.status_code == 200 else r.text)


def post_ticket(body, headers=None):
    return httpx.post(
        f"{GATEWAY}/livekit/support/tickets",
        json=body,
        headers=headers or {},
        timeout=60,
    )


def main():
    print("=" * 76)
    print("SUPPORT TICKET - GUEST AUR LOGIN, DONO")
    print("=" * 76)

    # =====================================================
    print("\n--- 1. GUEST: email ke baghair rad ho ---")
    # =====================================================
    r = post_ticket({"subject": "guest bina email", "message": "x"})
    chk("bina email 422", r.status_code == 422, f"HTTP {r.status_code}")

    # =====================================================
    print("\n--- 2. GUEST: kharab email rad ho ---")
    # =====================================================
    r = post_ticket({
        "subject": "kharab email",
        "message": "x",
        "email": "ye-email-nahi-hai",
    })
    chk("kharab email 422", r.status_code == 422, f"HTTP {r.status_code}")

    # =====================================================
    print("\n--- 3. GUEST: email ke sath ban jaye ---")
    # =====================================================
    r = post_ticket({
        "subject": "Guest cannot hear the assistant",
        "message": "Bina login madad chahiye.",
        "email": GUEST_EMAIL,
    })
    chk("guest ticket 201", r.status_code == 201, f"HTTP {r.status_code}")

    if r.status_code == 201:
        gt = r.json().get("ticket_id")
        made.append(gt)
        print(f"        guest ticket: {gt}")

        code, doc = erp_get(f"/api/resource/Issue/{gt}")
        chk("ERPNext mein mojood", code == 200, f"HTTP {code}")
        if code == 200:
            got = doc["data"].get("raised_by")
            chk("raised_by = guest ka email", got == GUEST_EMAIL, str(got))
            gdesc = doc["data"].get("description") or ""
            chk("guest ka email description mein bhi",
                GUEST_EMAIL in gdesc, "<- raised_by ke ilawa")

    # =====================================================
    print("\n--- 4. login (gateway se) ---")
    # =====================================================
    r = httpx.post(
        f"{GATEWAY}/auth/login",
        data={"username": EMAIL, "password": PASSWORD},
        timeout=40,
    )
    chk("login", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code != 200:
        print("  ", r.text[:200])
        return

    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # =====================================================
    print("\n--- 5. LOGIN: email ke baghair bhi ban jaye ---")
    # =====================================================
    r = post_ticket({"subject": SUBJECT, "message": MESSAGE}, auth)
    chk("HTTP 201", r.status_code == 201, f"HTTP {r.status_code}")
    if r.status_code != 201:
        print("  ", r.text[:300])
        return

    body = r.json()
    ticket = body.get("ticket_id")
    made.append(ticket)

    print(f"        jawab: {body}")
    chk("ticket number mila", bool(ticket), str(ticket))
    chk("ISS- se shuru", str(ticket).startswith("ISS-"), str(ticket))
    chk("status Open", body.get("status") == "Open", str(body.get("status")))

    # =====================================================
    print("\n--- 6. ERPNext se SEEDHA tasdeeq ---")
    # =====================================================
    code, doc = erp_get(f"/api/resource/Issue/{ticket}")
    chk("ERPNext mein mojood", code == 200, f"HTTP {code}")

    if code == 200:
        d = doc["data"]
        print(f"        subject   = {d.get('subject')!r}")
        print(f"        raised_by = {d.get('raised_by')}")
        print(f"        type      = {d.get('issue_type')}"
              f"   status = {d.get('status')}")
        chk("subject sahi", d.get("subject") == SUBJECT)
        chk("raised_by account ka email", d.get("raised_by") == EMAIL,
            str(d.get("raised_by")))
        chk("issue_type = Support Request",
            d.get("issue_type") == "Support Request",
            str(d.get("issue_type")))
        chk("message description mein",
            "greeting" in (d.get("description") or "").lower(),
            (d.get("description") or "")[:50])

        # Email aur naam description mein bhi - taake school ko
        # ticket kholte hi nazar aayein
        desc = d.get("description") or ""
        chk("email description mein bhi", EMAIL in desc,
            "<- raised_by ke ilawa")
        chk("bhejne wale ka naam description mein",
            "From:" in desc and len(desc.split("From:")[1][:40].strip()) > 3,
            desc.split("From:")[1][:44].strip() if "From:" in desc else "GHAYAB")

    # =====================================================
    print("\n--- 7. LOGIN: doosre ka email bhejna na chale ---")
    # =====================================================
    r = post_ticket({
        "subject": "Spoof attempt",
        "message": "doosre ke naam par",
        "email": "shikaar@example.com",
    }, auth)

    if r.status_code == 201:
        spoof = r.json().get("ticket_id")
        made.append(spoof)
        code, doc = erp_get(f"/api/resource/Issue/{spoof}")
        got = doc["data"].get("raised_by") if code == 200 else "?"
        chk("bheja hua email nazarandaz, account ka laga",
            got == EMAIL, f"raised_by={got}")
    else:
        chk("spoof request bani", False, f"HTTP {r.status_code}")

    # =====================================================
    print("\n--- 8. 'mere tickets' - guest ka na dikhe ---")
    # =====================================================
    r = httpx.get(f"{GATEWAY}/livekit/support/tickets",
                  headers=auth, timeout=40)
    chk("HTTP 200", r.status_code == 200, f"HTTP {r.status_code}")

    if r.status_code == 200:
        rows = r.json()
        ids = [x.get("name") for x in rows]
        print(f"        {len(rows)} ticket: {ids[:5]}")
        chk("apna ticket list mein", ticket in ids)
        chk("guest ka ticket list mein NAHI",
            all(x.get("name") != made[0] for x in rows),
            "<- doosre ka data leak nahi hota")

    # =====================================================
    print("\n--- 9. bina token list na mile ---")
    # =====================================================
    r = httpx.get(f"{GATEWAY}/livekit/support/tickets", timeout=40)
    chk("bina login 401", r.status_code == 401, f"HTTP {r.status_code}")

    # =====================================================
    print("\n--- 10. chhota subject rad ho ---")
    # =====================================================
    r = post_ticket({"subject": "ab", "message": "too short"}, auth)
    chk("chhota subject 422", r.status_code == 422, f"HTTP {r.status_code}")

    # =====================================================
    print("\n--- safai ---")
    # =====================================================
    for t in made:
        d = httpx.delete(f"{ERP}/api/resource/Issue/{t}",
                         headers=ERP_HEADERS, timeout=30)
        print(f"  {t} delete -> HTTP {d.status_code}")

    print("\n" + "=" * 76)
    print(f"  PASS: {p}   FAIL: {f}")
    print("=" * 76)


main()
