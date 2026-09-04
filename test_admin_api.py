"""
Admin endpoints: kaam karte hain, aur SIRF admin ko milte hain.

Sab se ahem cheez security hai - ek parent ko admin ka data kabhi
nahi milna chahiye. Pehle GET /escalations/ par sirf current_user
laga hua tha, yaani koi bhi logged-in parent saari escalations
dekh sakta tha.
"""
import json
import sys

import httpx

GATEWAY = "http://localhost:9000"
ADMIN = ("admin@vocira.com", "Admin@1234")
PARENT = ("ahmed@test.com", "Test@1234")

p = f = 0


def chk(label, cond, extra=""):
    global p, f
    if cond:
        print(f"  PASS  {label}  {extra}"); p += 1
    else:
        print(f"  FAIL  {label}  {extra}"); f += 1


def login(email, password):
    r = httpx.post(
        f"{GATEWAY}/auth/login",
        data={"username": email, "password": password},
        timeout=30,
    )
    if r.status_code != 200:
        return None, f"HTTP {r.status_code} {r.text[:90]}"
    return r.json().get("access_token"), None


def get(path, token, **kw):
    return httpx.get(
        f"{GATEWAY}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        **kw,
    )


print("=" * 76)
print("ADMIN API")
print("=" * 76)

print("\n--- 1. login ---")
admin_token, err = login(*ADMIN)
chk("admin login", admin_token is not None, err or "")
parent_token, err = login(*PARENT)
chk("parent login", parent_token is not None, err or "")

if not admin_token or not parent_token:
    print("\n!! login ke baghair aage nahi ja sakte")
    sys.exit(1)

print("\n--- 2. admin ko data milta hai ---")

r = get("/livekit/admin/stats", admin_token)
chk("GET /admin/stats", r.status_code == 200, f"HTTP {r.status_code}")
if r.status_code == 200:
    s = r.json()
    print(f"        today={s['today']}  week={s['week']}  total={s['total']}"
          f"  escalated={s['escalated']}  sessions={s['sessions']}")
    chk("asli ginti (jhoota 128 nahi)", s["total"] > 0, f"total={s['total']}")
    chk("7 din ka chart", len(s["queriesPerDay"]) == 7,
        str([d["value"] for d in s["queriesPerDay"]]))
    chk("escalation rate 100 banta hai",
        sum(x["value"] for x in s["escalationRate"]) in (99, 100, 101),
        str(s["escalationRate"]))

r = get("/livekit/admin/queries", admin_token, params={"limit": 5})
chk("GET /admin/queries", r.status_code == 200, f"HTTP {r.status_code}")
if r.status_code == 200:
    q = r.json()
    chk("sawal mile", len(q) > 0, f"{len(q)} rows")
    if q:
        chk("jodi bani (sawal + jawab)",
            any(x["response"] != "—" for x in q))
        print(f"        misaal: {q[0]['question'][:44]!r}")
        print(f"             -> {q[0]['response'][:44]!r}")

r = get("/livekit/admin/escalations", admin_token)
chk("GET /admin/escalations", r.status_code == 200, f"HTTP {r.status_code}")
if r.status_code == 200:
    e = r.json()
    print(f"        {len(e)} escalations")
    if e:
        chk("escalation ke sath sawal bhi", "question" in e[0])

print("\n--- 2b. knowledge base ---")
r = get("/livekit/admin/knowledge", admin_token)
chk("GET /admin/knowledge", r.status_code == 200, f"HTTP {r.status_code}")
if r.status_code == 200:
    idx = r.json().get("index", {})
    print(f"        vectors={idx.get('vectors')}  "
          f"model={idx.get('embedding_model')}  "
          f"dim={idx.get('embedding_dimension')}  "
          f"match={idx.get('dimension_match')}")
    chk("index mein vectors hain", (idx.get("vectors") or 0) > 0,
        str(idx.get("vectors")))
    chk("dimension match", idx.get("dimension_match") is True,
        str(idx.get("dimension_match")))

print("\n--- 3. PARENT ko admin data NAHI milna chahiye ---")

for path in ("/livekit/admin/stats",
             "/livekit/admin/queries",
             "/livekit/admin/escalations",
             "/livekit/admin/knowledge",
             "/livekit/escalations/"):
    r = get(path, parent_token)
    chk(f"parent -> {path}", r.status_code == 403,
        f"HTTP {r.status_code}"
        + ("  <- LEAK!" if r.status_code == 200 else ""))

print("\n--- 4. bina token ---")
for path in ("/livekit/admin/stats", "/livekit/admin/escalations"):
    r = httpx.get(f"{GATEWAY}{path}", timeout=30)
    chk(f"no token -> {path}", r.status_code in (401, 403),
        f"HTTP {r.status_code}")

print("\n" + "=" * 76)
print(f"  PASS: {p}   FAIL: {f}")
print("=" * 76)
