"""
Knowledge base: upload, note, list, delete - aur us ke baad VOCIRA
waqai us data se jawab deta hai ya nahi.

Sab se ahem hissa security ka hai: filename user ka bheja hua hota
hai. "../../.env" jaisa naam data folder se bahar likh sakta hai,
is liye us par do chhanniyan hain (safe_filename + _resolve).
"""

import io
import os
import time

import httpx

GATEWAY = "http://localhost:9000"
ADMIN = ("admin@vocira.com", "Admin@1234")
PARENT = ("muhmmadahmed763@edu.com", "Test@1234")

DATA = os.path.join(
    "backend", "microservices", "livekit_Rag_services",
    "services", "rag_engine", "data",
)

NOTE_TITLE = "Vocira upload test policy"
NOTE_TEXT = (
    "The purple gate rule: students may enter through the purple gate "
    "only between seven and eight in the morning. This is a test "
    "document added by test_knowledge_upload.py."
)

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
    print("KNOWLEDGE BASE - UPLOAD / NOTE / LIST / DELETE")
    print("=" * 76)

    at = login(*ADMIN)
    chk("admin login", at is not None)
    if not at:
        return
    auth = {"Authorization": f"Bearer {at}"}

    # =====================================================
    print("\n--- 1. sirf admin ---")
    # =====================================================
    pt = login(*PARENT)
    for path, method in [
        ("/livekit/admin/knowledge/documents", "GET"),
        ("/livekit/admin/knowledge/notes", "POST"),
    ]:
        r = httpx.request(method, f"{GATEWAY}{path}",
                          headers={"Authorization": f"Bearer {pt}"},
                          json={"title": "x" * 5, "text": "y" * 20},
                          timeout=40)
        chk(f"parent -> {path.split('/')[-1]} 403",
            r.status_code == 403, f"HTTP {r.status_code}")

    # =====================================================
    print("\n--- 2. list chalti hai ---")
    # =====================================================
    r = httpx.get(f"{GATEWAY}/livekit/admin/knowledge/documents",
                  headers=auth, timeout=60)
    chk("HTTP 200", r.status_code == 200, f"HTTP {r.status_code}")
    before = r.json() if r.status_code == 200 else {}
    print(f"        pehle: {before.get('total')} documents, "
          f"{before.get('chunks')} chunks")

    if before.get("documents"):
        d = before["documents"][0]
        for key in ("name", "kind", "size", "modified", "chunks", "indexed"):
            chk(f"document mein {key}", key in d)

    # =====================================================
    print("\n--- 3. SECURITY: file folder se bahar na likhe ---")
    # =====================================================
    nasty = [
        "../../../../evil.txt",
        "..\\..\\..\\evil.txt",
        "....//evil.txt",
        "/etc/passwd.txt",
    ]
    for name in nasty:
        files = {"file": (name, b"should never land outside", "text/plain")}
        r = httpx.post(f"{GATEWAY}/livekit/admin/knowledge/documents",
                       headers=auth, files=files, timeout=60)

        landed = r.json().get("name") if r.status_code == 201 else None
        if landed:
            made.append(landed)

        # ya to rad ho, ya mehfooz naam se ANDAR hi rahe
        safe = (
            r.status_code == 422
            or (landed and "/" not in landed and "\\" not in landed
                and not landed.startswith(".."))
        )
        chk(f"{name!r:28} sambhala", safe,
            f"HTTP {r.status_code} -> {landed}")

    # data folder se bahar kuch bana to nahi
    outside = os.path.exists(os.path.join(DATA, "..", "..", "evil.txt"))
    chk("folder se BAHAR kuch nahi bana", not outside)

    # =====================================================
    print("\n--- 4. ghalat qism rad ho ---")
    # =====================================================
    for name, why in [("virus.exe", "exe"), ("data.csv", "csv")]:
        r = httpx.post(f"{GATEWAY}/livekit/admin/knowledge/documents",
                       headers=auth,
                       files={"file": (name, b"x" * 50, "application/octet-stream")},
                       timeout=60)
        chk(f"{why} rad", r.status_code == 422, f"HTTP {r.status_code}")

    # =====================================================
    print("\n--- 5. asli upload ---")
    # =====================================================
    up_name = "vocira_test_upload.txt"
    body = b"Test upload from test_knowledge_upload.py. Library closes at five."
    r = httpx.post(f"{GATEWAY}/livekit/admin/knowledge/documents",
                   headers=auth,
                   files={"file": (up_name, body, "text/plain")},
                   timeout=60)
    chk("upload 201", r.status_code == 201, f"HTTP {r.status_code}")
    if r.status_code == 201:
        made.append(r.json()["name"])
        on_disk = os.path.join(DATA, "text_files", up_name)
        chk("file waqai disk par", os.path.isfile(on_disk), on_disk)

    # =====================================================
    print("\n--- 6. note ---")
    # =====================================================
    r = httpx.post(f"{GATEWAY}/livekit/admin/knowledge/notes",
                   headers=auth,
                   json={"title": NOTE_TITLE, "text": NOTE_TEXT},
                   timeout=60)
    chk("note 201", r.status_code == 201, f"HTTP {r.status_code}")
    note_name = None
    if r.status_code == 201:
        note_name = r.json()["name"]
        made.append(note_name)
        print(f"        bani: {note_name}")

    # chhota note rad ho
    r = httpx.post(f"{GATEWAY}/livekit/admin/knowledge/notes",
                   headers=auth, json={"title": "ab", "text": "short"},
                   timeout=40)
    chk("chhota note rad", r.status_code == 422, f"HTTP {r.status_code}")

    # =====================================================
    print("\n--- 7. list mein 'not indexed' nazar aaye ---")
    # =====================================================
    r = httpx.get(f"{GATEWAY}/livekit/admin/knowledge/documents",
                  headers=auth, timeout=60)
    rows = r.json().get("documents", [])
    names = [d["name"] for d in rows]
    chk("naya upload list mein", up_name in names)
    if note_name:
        chk("note list mein", note_name in names)

    fresh = next((d for d in rows if d["name"] == up_name), None)
    chk("abhi indexed nahi", fresh is not None and fresh["indexed"] is False,
        "<- sync se pehle yehi hona chahiye")

    # =====================================================
    print("\n--- 8. sync, phir VOCIRA se poochein ---")
    # =====================================================
    r = httpx.post(f"{GATEWAY}/livekit/admin/knowledge/sync",
                   headers=auth, timeout=60)
    chk("sync shuru", r.status_code in (200, 202), f"HTTP {r.status_code}")

    state = "?"
    for _ in range(40):
        time.sleep(3)
        k = httpx.get(f"{GATEWAY}/livekit/admin/knowledge",
                      headers=auth, timeout=60).json()
        state = k.get("last_sync", {}).get("state")
        if state in ("success", "error"):
            break
    chk("sync mukammal", state == "success", f"state={state}")

    if state == "success":
        r = httpx.get(f"{GATEWAY}/livekit/admin/knowledge/documents",
                      headers=auth, timeout=60)
        rows = r.json().get("documents", [])
        now = next((d for d in rows if d["name"] == up_name), None)
        chk("ab chunks ki ginti aa gayi",
            now is not None and now["indexed"] and (now["chunks"] or 0) > 0,
            f"chunks={now.get('chunks') if now else '?'}")

        # ASLI IMTIHAN: kya VOCIRA is naye data se jawab deta hai
        from backend.microservices.livekit_Rag_services.services.rag_engine.query import (
            ask_vocira,
        )
        from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
            connect_existing_store,
        )
        import asyncio, contextlib
        noise = io.StringIO()

        async def ask(q):
            with contextlib.redirect_stdout(noise):
                r = connect_existing_store()
                return await ask_vocira(retriever=r, user_query=q)

        answer = asyncio.run(ask("What is the purple gate rule?"))
        print(f"\n        sawal : What is the purple gate rule?")
        print(f"        jawab : {answer[:150]}")
        chk("VOCIRA naye note se jawab deta hai",
            "purple" in answer.lower() or "gate" in answer.lower(),
            "<- yehi poora maqsad tha")

    # =====================================================
    print("\n--- 9. delete ---")
    # =====================================================
    for name in list(made):
        r = httpx.delete(
            f"{GATEWAY}/livekit/admin/knowledge/documents/{name}",
            headers=auth, timeout=40,
        )
        ok = r.status_code in (200, 404)
        print(f"  {'PASS' if ok else 'FAIL'}  delete {name}  HTTP {r.status_code}")
        if ok:
            globals()['p'] = p + 1
        else:
            globals()['f'] = f + 1

    # index ko wapis saaf halat mein le aayein
    httpx.post(f"{GATEWAY}/livekit/admin/knowledge/sync",
               headers=auth, timeout=60)
    print("  (safai ke baad sync dobara chala di)")

    print("\n" + "=" * 76)
    print(f"  PASS: {p}   FAIL: {f}")
    print("=" * 76)


main()
