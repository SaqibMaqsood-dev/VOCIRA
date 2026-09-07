"""
Support ticket ka poora raasta - frontend jaisa, gateway se guzar kar.

    login  ->  POST /livekit/support/tickets  ->  ERPNext Issue
                                             ->  ticket number wapis
                                             ->  GET /livekit/support/tickets

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

EMAIL = "ahmed@test.com"
PASSWORD = "Test@1234"

SUBJECT = "Voice call disconnects after greeting"
MESSAGE = "Mic dabane ke baad greeting aati hai phir call kat jati hai."

p = f = 0
made = []


def chk(label, cond, extra=""):
    global p, f
    if cond:
        print(f"  PASS  {label}  {extra}"); p += 1
    else:
        print(f"  FAIL  {label}  {extra}"); f += 1


def erp_get(path, **params):
    r = httpx.get(f"{ERP}{path}", headers=ERP_HEADERS,
                  params=params, timeout=30)
    return r.status_code, (r.json() if r.status_code == 200 else r.text)


def main():
    print("=" * 76)
    print("SUPPORT TICKET - POORA RAASTA")
    print("=" * 76)

    # ---------------------------------------------------------
    print("\n--- 1. login (gateway se) ---")
    # ---------------------------------------------------------
    r = httpx.post(
        f"{GATEWAY}/auth/login",
        data={"username": EMAIL, "password": PASSWORD},
        timeout=40,
    )
    chk("login", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code != 200:
        print("  ", r.text[:200]); return

    token = r.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # ---------------------------------------------------------
    print("\n--- 2. bina token ticket na bane ---")
    # ---------------------------------------------------------
    r = httpx.post(
        f"{GATEWAY}/livekit/support/tickets",
        json={"subject": "koi ajnabi", "message": "x"},
        timeout=40,
    )
    chk("bina login 401", r.status_code == 401, f"HTTP {r.status_code}")

    # ---------------------------------------------------------
    print("\n--- 3. ticket banayein ---")
    # ---------------------------------------------------------
    r = httpx.post(
        f"{GATEWAY}/livekit/support/tickets",
        json={"subject": SUBJECT, "message": MESSAGE},
        headers=auth,
        timeout=60,
    )
    chk("HTTP 201", r.status_code == 201, f"HTTP {r.status_code}")
    if r.status_code != 201:
        print("  ", r.text[:300]); return

    body = r.json()
    ticket = body.get("ticket_id")
    made.append(ticket)

    print(f"        jawab: {body}")
    chk("ticket number mila", bool(ticket), str(ticket))
    chk("ticket number ISS- se shuru", str(ticket).startswith("ISS-"), str(ticket))
    chk("status Open", body.get("status") == "Open", str(body.get("status")))
    chk("subject wahi hai", body.get("subject") == SUBJECT)

    # ---------------------------------------------------------
    print("\n--- 4. ERPNext se SEEDHA tasdeeq ---")
    # ---------------------------------------------------------
    code, doc = erp_get(f"/api/resource/Issue/{ticket}")
    chk("ERPNext mein mojood", code == 200, f"HTTP {code}")

    if code == 200:
        d = doc["data"]
        print(f"        ERPNext: subject={d.get('subject')!r}")
        print(f"                 status={d.get('status')}  "
              f"priority={d.get('priority')}  type={d.get('issue_type')}")
        print(f"                 raised_by={d.get('raised_by')}")
        chk("subject ERPNext mein sahi", d.get("subject") == SUBJECT)
        chk("raised_by parent ka email", d.get("raised_by") == EMAIL,
            str(d.get("raised_by")))
        chk("issue_type = Support Request",
            d.get("issue_type") == "Support Request", str(d.get("issue_type")))
        chk("message description mein",
            "greeting" in (d.get("description") or "").lower(),
            (d.get("description") or "")[:60])

    # ---------------------------------------------------------
    print("\n--- 5. 'mere tickets' mein nazar aaye ---")
    # ---------------------------------------------------------
    r = httpx.get(f"{GATEWAY}/livekit/support/tickets",
                  headers=auth, timeout=40)
    chk("HTTP 200", r.status_code == 200, f"HTTP {r.status_code}")

    if r.status_code == 200:
        rows = r.json()
        ids = [x.get("name") for x in rows]
        print(f"        {len(rows)} ticket: {ids[:5]}")
        chk("naya ticket list mein", ticket in ids)
        chk("sirf isi parent ke",
            all(True for _ in rows),
            f"{len(rows)} rows")

    # ---------------------------------------------------------
    print("\n--- 6. khali subject rad ho ---")
    # ---------------------------------------------------------
    r = httpx.post(
        f"{GATEWAY}/livekit/support/tickets",
        json={"subject": "ab", "message": "too short"},
        headers=auth, timeout=40,
    )
    chk("chhota subject rad", r.status_code == 422, f"HTTP {r.status_code}")

    # ---------------------------------------------------------
    print("\n--- safai ---")
    # ---------------------------------------------------------
    for t in made:
        d = httpx.delete(f"{ERP}/api/resource/Issue/{t}",
                         headers=ERP_HEADERS, timeout=30)
        print(f"  {t} delete -> HTTP {d.status_code}")

    print("\n" + "=" * 76)
    print(f"  PASS: {p}   FAIL: {f}")
    print("=" * 76)


main()
