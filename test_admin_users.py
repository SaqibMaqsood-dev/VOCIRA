"""
Admin panel ka Users page - parents ke accounts sambhalna.

Pehle VOCIRA ke accounts dekhne ya badalne ka koi raasta hi nahi tha:
na koi page, na password reset, na "forgot password". Sab kuch psql
ya script se karna parta tha.

Ye endpoints AUTH service mein hain (livekit mein nahi) kyunke
password hashing argon2 se hoti hai aur wo sirf auth ke venv mein
mojood hai. Gateway par raasta /auth/admin/users banta hai.
"""

import httpx

GATEWAY = "http://localhost:9000"
BASE = f"{GATEWAY}/auth/admin/users"

ADMIN = ("admin@vocira.com", "Admin@1234")
PARENT = ("ahmed@test.com", "Test@1234")

NEW_EMAIL = "test.parent@vocira-test.com"
NEW_PASS = "Parent@1234"
NEW_PASS2 = "Changed@5678"

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


def login(email, pw):
    r = httpx.post(f"{GATEWAY}/auth/login",
                   data={"username": email, "password": pw}, timeout=40)
    return r.json()["access_token"] if r.status_code == 200 else None


def main():
    print("=" * 76)
    print("ADMIN - USERS")
    print("=" * 76)

    at = login(*ADMIN)
    chk("admin login", at is not None)
    if not at:
        return
    auth = {"Authorization": f"Bearer {at}"}

    pt = login(*PARENT)
    chk("parent login", pt is not None)
    parent_auth = {"Authorization": f"Bearer {pt}"}

    # =====================================================
    print("\n--- 1. sirf admin ke liye ---")
    # =====================================================
    for method, path in [("GET", ""), ("POST", ""), ("GET", "/roles")]:
        r = httpx.request(method, f"{BASE}{path}", headers=parent_auth,
                          json={"email": "x@y.com", "name": "X",
                                "password": "Whatever1234"},
                          timeout=40)
        chk(f"parent {method:5} {path or '/':8} 403",
            r.status_code == 403, f"HTTP {r.status_code}")

    r = httpx.get(BASE, timeout=40)
    chk("bina token 401", r.status_code == 401, f"HTTP {r.status_code}")

    # =====================================================
    print("\n--- 2. list ---")
    # =====================================================
    r = httpx.get(BASE, headers=auth, timeout=40)
    chk("HTTP 200", r.status_code == 200, f"HTTP {r.status_code}")

    if r.status_code == 200:
        body = r.json()
        print(f"        {body['total']} accounts, {body['linked']} guardian se juRe")
        for u in body["users"]:
            print(f"          {u['email']:<26} {u['role'] or '-':<10} {u['parent_id'] or '-'}")

        chk("ahmed list mein",
            any(u["email"] == "ahmed@test.com" for u in body["users"]))

        ahmed = next(u for u in body["users"] if u["email"] == "ahmed@test.com")
        chk("parent_id sahi", ahmed["parent_id"] == "EDU-GRD-2026-00002",
            str(ahmed["parent_id"]))

        # SECURITY: password hash kabhi bahar na jaye
        leaked = [k for u in body["users"] for k in u
                  if "password" in k.lower() or "hash" in k.lower()]
        chk("password hash bahar NAHI jata", not leaked, str(leaked))

    # =====================================================
    print("\n--- 3. roles ---")
    # =====================================================
    r = httpx.get(f"{BASE}/roles", headers=auth, timeout=40)
    chk("roles 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        names = [x["name"] for x in r.json()]
        print(f"        {names}")
        chk("guardian role mojood", "guardian" in names)

    # =====================================================
    print("\n--- 4. naya account ---")
    # =====================================================
    r = httpx.post(BASE, headers=auth, timeout=40, json={
        "email": NEW_EMAIL, "name": "Test Parent",
        "password": NEW_PASS, "parent_id": "EDU-GRD-2026-00003",
        "role": "guardian",
    })
    chk("create 201", r.status_code == 201, f"HTTP {r.status_code}")

    uid = None
    if r.status_code == 201:
        uid = r.json()["user_id"]
        made.append(uid)
        print(f"        {r.json()}")

    # ASLI IMTIHAN: naya banda login kar sakta hai?
    chk("naya account login kar sakta hai",
        login(NEW_EMAIL, NEW_PASS) is not None)

    # dobara wahi email
    r = httpx.post(BASE, headers=auth, timeout=40, json={
        "email": NEW_EMAIL, "name": "Duplicate", "password": NEW_PASS})
    chk("wahi email dobara 409", r.status_code == 409, f"HTTP {r.status_code}")

    # kamzor password
    r = httpx.post(BASE, headers=auth, timeout=40, json={
        "email": "weak@vocira-test.com", "name": "Weak", "password": "abc"})
    chk("chhota password 422", r.status_code == 422, f"HTTP {r.status_code}")

    # anjaan role
    r = httpx.post(BASE, headers=auth, timeout=40, json={
        "email": "role@vocira-test.com", "name": "Bad Role",
        "password": NEW_PASS, "role": "superuser"})
    chk("anjaan role 422", r.status_code == 422, f"HTTP {r.status_code}")

    if not uid:
        print("\n  create fail - aage ke test chhore")
        return

    # =====================================================
    print("\n--- 5. parent_id badalna ---")
    # =====================================================
    r = httpx.patch(f"{BASE}/{uid}", headers=auth, timeout=40,
                    json={"parent_id": "EDU-GRD-2026-00004", "name": "Renamed Parent"})
    chk("patch 200", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code == 200:
        chk("parent_id badla", r.json()["parent_id"] == "EDU-GRD-2026-00004",
            str(r.json()["parent_id"]))
        chk("naam badla", r.json()["name"] == "Renamed Parent")

    # khali bhejne se link hat jaye
    r = httpx.patch(f"{BASE}/{uid}", headers=auth, timeout=40,
                    json={"parent_id": ""})
    chk("khali parent_id -> null",
        r.status_code == 200 and r.json()["parent_id"] is None,
        str(r.json().get("parent_id")))

    # wapis laga dein
    httpx.patch(f"{BASE}/{uid}", headers=auth, timeout=40,
                json={"parent_id": "EDU-GRD-2026-00003"})

    # =====================================================
    print("\n--- 6. password reset ---")
    # =====================================================
    r = httpx.post(f"{BASE}/{uid}/password", headers=auth, timeout=40,
                   json={"password": NEW_PASS2})
    chk("reset 200", r.status_code == 200, f"HTTP {r.status_code}")

    chk("naya password chalta hai", login(NEW_EMAIL, NEW_PASS2) is not None)
    chk("purana password ab NAHI chalta", login(NEW_EMAIL, NEW_PASS) is None)

    r = httpx.post(f"{BASE}/{uid}/password", headers=auth, timeout=40,
                   json={"password": "abc"})
    chk("chhota password 422", r.status_code == 422, f"HTTP {r.status_code}")

    # =====================================================
    print("\n--- 7. naya parent apne bachche dekh sakta hai ---")
    # =====================================================
    nt = login(NEW_EMAIL, NEW_PASS2)
    if nt:
        import asyncio, io, contextlib
        from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import (
            ERPService,
        )
        svc = ERPService()

        async def kids():
            with contextlib.redirect_stdout(io.StringIO()):
                return await svc.get_parent_students("EDU-GRD-2026-00003")

        rows = asyncio.run(kids()) or []
        names = [k.get("student_name") for k in rows]
        chk("EDU-GRD-2026-00003 ke bachche mile", bool(names), str(names))

    # =====================================================
    print("\n--- 8. admin apna account na hata sake ---")
    # =====================================================
    r = httpx.get(BASE, headers=auth, timeout=40)
    me = next((u for u in r.json()["users"]
               if u["email"] == "admin@vocira.com"), None)
    if me:
        d = httpx.delete(f"{BASE}/{me['user_id']}", headers=auth, timeout=40)
        chk("apna account delete 400", d.status_code == 400,
            f"HTTP {d.status_code}")

    # =====================================================
    print("\n--- 9. safai ---")
    # =====================================================
    for u in made:
        d = httpx.delete(f"{BASE}/{u}", headers=auth, timeout=40)
        chk(f"delete {u[:8]}", d.status_code == 200, f"HTTP {d.status_code}")

    chk("hataya hua account login NAHI kar sakta",
        login(NEW_EMAIL, NEW_PASS2) is None)

    print("\n" + "=" * 76)
    print(f"  PASS: {p}   FAIL: {f}")
    print("=" * 76)


main()
