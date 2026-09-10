"""Phase 5: kya do calls ek sath chal sakti hain?"""
import asyncio, io, contextlib, time, urllib.request, json, base64

RMQ = "http://localhost:15672/api/queues/%2F/vocira_queue"
AUTH = "Basic " + base64.b64encode(b"guest:guest").decode()


def queue_state():
    req = urllib.request.Request(RMQ, headers={"Authorization": AUTH})
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read().decode())
    return d.get("consumers", 0), d.get("messages_ready", 0), d.get("messages_unacknowledged", 0)


async def main():
    # SQLAlchemy ko saare models chahiye warna Session.messages ka
    # relationship resolve nahi hota (asli service mein main.py ye
    # import karta hai)
    from backend.microservices.livekit_Rag_services.models import (  # noqa: F401
        session_model, message_model, escalation_model,
    )
    from backend.microservices.auth_services.models import (  # noqa: F401
        user_model, role_model, refresh_tokken, permission_model,
        role_permision_model,
    )
    from backend.microservices.livekit_Rag_services.services.router_services.session_service import SessionService
    from backend.helper_functions.database.session import SessionLocal

    ss = SessionService()
    noise = io.StringIO()

    print("=" * 70)
    print("PHASE 5: CONCURRENT CALLS")
    print("=" * 70)

    c, ready, unacked = queue_state()
    print(f"\nshuru mein  : consumers={c}  qatar={ready}  chal rahi={unacked}")
    if c == 0:
        print("  worker nahi chal raha - test bemani hai")
        return

    # ---- teen sessions ek sath banayein ----
    print("\n--- teen sessions ek sath bana rahe hain ---")
    t0 = time.perf_counter()
    ids = []
    for i in range(3):
        async with SessionLocal() as db:
            with contextlib.redirect_stdout(noise):
                s = await ss.create_session(db=db, user_id=None)
        ids.append(str(s.id))
        print(f"  {i+1}. {s.id}")
    print(f"  ({(time.perf_counter()-t0):.1f}s)")

    # ---- worker ko uthane ka waqt dein ----
    print("\n--- 20 second: worker inhe uthata hai ---")
    for _ in range(10):
        await asyncio.sleep(2)
        c, ready, unacked = queue_state()
        print(f"  qatar={ready}  chal rahi={unacked}")
        if unacked >= 2:
            break

    print()
    print("=" * 70)
    if unacked >= 2:
        print(f"  PASS  {unacked} calls EK SATH chal rahi hain")
        print("        (pehle prefetch_count=1 tha - hamesha 1 se zyada na hoti)")
    elif unacked == 1 and ready >= 1:
        print("  FAIL  ek chal rahi hai, baqi qatar mein - concurrency nahi lagi")
    else:
        print(f"  ?     qatar={ready} chal rahi={unacked} - dobara dekhein")
    print("=" * 70)

    # ---- safai ----
    print("\n--- sessions band kar rahe hain ---")
    async with SessionLocal() as db:
        from sqlalchemy import text
        await db.execute(text(
            "UPDATE sessions SET status='closed', end_at=NOW() WHERE status='active'"))
        await db.commit()
    print("  ho gaya")


asyncio.run(main())
