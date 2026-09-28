# -*- coding: utf-8 -*-
"""End-to-end check of "connect me to a person".

Opens the admin notification socket exactly as the admin panel does,
then publishes a handoff the way the voice pipeline does, and waits
to see whether it actually arrives. That is the part nobody can see
from the caller's side - the caller only ever hears silence when it
does not.
"""
import asyncio
import json
import time
import uuid

import jwt
import websockets

from backend.microservices.livekit_Rag_services.core.config import settings
from backend.microservices.livekit_Rag_services.core.rabitmq import RabbitMQ

ADMIN_ID = "fb351625-75fc-49b1-8467-9c85ffd9a232"
SECRET = "vocira_local_dev_secret_9f3a2b7c1d4e6f8a0b2c4d6e8f0a2b4c"


def admin_token() -> str:
    return jwt.encode(
        {
            "sub": "admin@vocira.com",
            "user_id": ADMIN_ID,
            "role": "admin",
            "name": "Admin",
            "exp": int(time.time()) + 3600,
        },
        SECRET,
        algorithm="HS256",
    )


async def main() -> None:
    failures = 0

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        if not passed:
            failures += 1
        print(f"  [{'PASS' if passed else 'FAIL'}] {name} {detail}")

    url = (
        "ws://127.0.0.1:8001/livekit/notifications/ws/admin"
        f"?token={admin_token()}"
    )

    try:
        socket = await asyncio.wait_for(websockets.connect(url), timeout=15)
    except Exception as error:
        check("admin socket opens", False, f"{type(error).__name__}: {error}")
        return

    check("admin socket opens", True)

    # A non-admin must not get onto this channel.
    guest_token = jwt.encode(
        {
            "sub": "g@x.com",
            "user_id": str(uuid.uuid4()),
            "role": "guardian",
            "exp": int(time.time()) + 3600,
        },
        SECRET,
        algorithm="HS256",
    )

    try:
        bad = await asyncio.wait_for(
            websockets.connect(
                "ws://127.0.0.1:8001/livekit/notifications/ws/admin"
                f"?token={guest_token}"
            ),
            timeout=10,
        )
        await bad.close()
        check("guardian is refused", False, "socket stayed open")
    except Exception:
        check("guardian is refused", True)

    # Now publish a handoff the way the pipeline does.
    session_id = str(uuid.uuid4())
    escalation_id = str(uuid.uuid4())

    rabbit = RabbitMQ()
    await rabbit.connect()

    await rabbit.publish_admin_handoff(
        {
            "event": "admin.call.handoff",
            "call_id": session_id,
            "session_id": session_id,
            "room_name": f"room-{session_id}",
            "caller_id": "92f96edf-d36a-47bb-9029-8aaa4cda8b35",
            "escalation_id": escalation_id,
            "caller_name": "Shahzaib Farooq",
            "question": "mujhe human ke saath connect kar do",
        }
    )
    print("  handoff published, waiting on the socket...")

    try:
        raw = await asyncio.wait_for(socket.recv(), timeout=20)
        payload = json.loads(raw)

        check(
            "admin receives the notification",
            payload.get("session_id") == session_id
            or payload.get("call_id") == session_id,
            f"-> event={payload.get('event')!r}",
        )
        print(f"         payload: {json.dumps(payload, ensure_ascii=False)[:160]}")
    except asyncio.TimeoutError:
        check("admin receives the notification", False, "nothing arrived in 20s")

    await socket.close()
    print(f"\n==== {failures} failure(s)")


if __name__ == "__main__":
    asyncio.run(main())
