"""
Admin panel: asli data aata hai, aur ghair-admin ko nahi milta.

Guard do jagah hai:

    frontend  AdminGuard  ->  role dekh kar raasta (tameez)
    backend   require_admin -> 403 (asli rok)

Yahan backend wali rok jaanchi jati hai - wahi ahem hai. Frontend ka
guard sirf ye karta hai ke ghalat user ko admin UI ki jhalak na
dikhe; us ka localStorage badal dena aasan hai aur us se kuch milta
bhi nahi.
"""

import httpx

GATEWAY = "http://localhost:9000"

ADMIN = ("admin@vocira.com", "Admin@1234")
PARENT = ("muhmmadahmed763@edu.com", "Test@1234")

ENDPOINTS = [
    "/livekit/admin/stats",
    "/livekit/admin/queries?limit=5",
    "/livekit/admin/escalations?limit=5",
    "/livekit/admin/knowledge",
]

p = f = 0


def chk(label, cond, extra=""):
    global p, f
    if cond:
        print(f"  PASS  {label}  {extra}")
        p += 1
    else:
        print(f"  FAIL  {label}  {extra}")
        f += 1


def login(email, pw):
    r = httpx.post(f"{GATEWAY}/auth/login",
                   data={"username": email, "password": pw}, timeout=40)
    return r.json()["access_token"] if r.status_code == 200 else None


def main():
    print("=" * 74)
    print("ADMIN PANEL")
    print("=" * 74)

    # =====================================================
    print("\n--- 1. bina token: sab band ---")
    # =====================================================
    for ep in ENDPOINTS:
        r = httpx.get(f"{GATEWAY}{ep}", timeout=40)
        chk(f"{ep.split('?')[0]:34} 401", r.status_code == 401,
            f"HTTP {r.status_code}")

    # =====================================================
    print("\n--- 2. parent ka token: 403 (asli rok) ---")
    # =====================================================
    pt = login(*PARENT)
    chk("parent login", pt is not None)

    if pt:
        for ep in ENDPOINTS:
            r = httpx.get(f"{GATEWAY}{ep}",
                          headers={"Authorization": f"Bearer {pt}"}, timeout=40)
            chk(f"{ep.split('?')[0]:34} 403", r.status_code == 403,
                f"HTTP {r.status_code}")

    # =====================================================
    print("\n--- 3. admin ka token: asli data ---")
    # =====================================================
    at = login(*ADMIN)
    chk("admin login", at is not None)
    if not at:
        return

    auth = {"Authorization": f"Bearer {at}"}

    r = httpx.get(f"{GATEWAY}/livekit/admin/stats", headers=auth, timeout=60)
    chk("stats 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        print(f"        today={d.get('today')}  week={d.get('week')}  "
              f"total={d.get('total')}  escalated={d.get('escalated')}  "
              f"sessions={d.get('sessions')}")
        for key in ("today", "week", "total", "escalated", "queriesPerDay"):
            chk(f"stats mein {key}", key in d)
        chk("queriesPerDay 7 din ka",
            isinstance(d.get("queriesPerDay"), list)
            and len(d["queriesPerDay"]) == 7,
            str(len(d.get("queriesPerDay") or [])))

    r = httpx.get(f"{GATEWAY}/livekit/admin/queries?limit=5",
                  headers=auth, timeout=60)
    chk("queries 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        rows = r.json()
        chk("queries mein records", len(rows) > 0, f"{len(rows)} rows")
        if rows:
            row = rows[0]
            for key in ("id", "user", "question", "response", "status",
                        "timestamp"):
                chk(f"query mein {key}", key in row)
            print(f"        misaal: {row['user']} - "
                  f"{str(row['question'])[:44]!r}")

    r = httpx.get(f"{GATEWAY}/livekit/admin/escalations?limit=5",
                  headers=auth, timeout=60)
    chk("escalations 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        rows = r.json()
        print(f"        {len(rows)} escalation")
        if rows:
            for key in ("id", "question", "status", "time"):
                chk(f"escalation mein {key}", key in rows[0])

    r = httpx.get(f"{GATEWAY}/livekit/admin/knowledge",
                  headers=auth, timeout=60)
    chk("knowledge 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        idx = d.get("index") or {}
        print(f"        index={idx.get('index')}  "
              f"vectors={idx.get('vectors')}  "
              f"model={idx.get('embedding_model')}")
        chk("index ki maloomat", "index" in d and "last_sync" in d)
        chk("vectors ginti aati hai", isinstance(idx.get("vectors"), int),
            str(idx.get("vectors")))

    # =====================================================
    print("\n--- 4. escalation ka status badalna ---")
    # =====================================================
    r = httpx.get(f"{GATEWAY}/livekit/admin/escalations?limit=1",
                  headers=auth, timeout=60)
    rows = r.json() if r.status_code == 200 else []

    if rows:
        eid = rows[0]["id"]
        was = rows[0]["status"]

        # new_status query parameter hai, body nahi - frontend bhi
        # aise hi bhejta hai
        u = httpx.patch(
            f"{GATEWAY}/livekit/admin/escalations/{eid}"
            f"/status?new_status=resolved",
            headers=auth, timeout=60,
        )
        chk("status resolved kiya", u.status_code in (200, 204),
            f"HTTP {u.status_code}")

        # wapis padh kar dekhein
        c = httpx.get(f"{GATEWAY}/livekit/admin/escalations?limit=100",
                      headers=auth, timeout=60)
        now = next((x for x in c.json() if x["id"] == eid), None)
        chk("DB mein waqai badla",
            now is not None and now["status"] == "resolved",
            f"{was} -> {now['status'] if now else '?'}")

        # jaisa tha waisa kar dein
        httpx.patch(f"{GATEWAY}/livekit/admin/escalations/{eid}"
                    f"/status?new_status={was}",
                    headers=auth, timeout=60)
        print(f"        wapis '{was}' kar diya")
    else:
        print("        koi escalation nahi - ye test chhora")

    # =====================================================
    print("\n--- 5. parent status badal na sake ---")
    # =====================================================
    if rows and pt:
        u = httpx.patch(
            f"{GATEWAY}/livekit/admin/escalations/{rows[0]['id']}"
            f"/status?new_status=closed",
            headers={"Authorization": f"Bearer {pt}"}, timeout=60,
        )
        chk("parent ko 403", u.status_code == 403, f"HTTP {u.status_code}")

    print("\n" + "=" * 74)
    print(f"  PASS: {p}   FAIL: {f}")
    print("=" * 74)


main()
