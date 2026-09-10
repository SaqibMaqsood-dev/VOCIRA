"""
Frontend ka LiveKit visualizer do cheezon par chalta hai:

  1. agent LiveKit ko "agent kind" ka participant nazar aaye
     (warna useVoiceAssistant() ko koi agent milta hi nahi)
  2. agent "lk.agent.state" attribute bheje
     (isi se listening / thinking / speaking dikhta hai)

Dono yahan check hote hain - token ke andar dekh kar, aur asli
room mein join kar ke.
"""
import asyncio
import base64
import io
import contextlib
import json
import os

from livekit import api, rtc

from backend.microservices.livekit_Rag_services.core.config import settings
from backend.microservices.livekit_Rag_services.services.livekit.livekit_services.livekit_room_service import (
    LivekitRoomServices,
)
from backend.microservices.livekit_Rag_services.services.livekit.livekit_services import (
    voice_pipeline,
)

noise = io.StringIO()
p = f = 0


def chk(label, cond, extra=""):
    global p, f
    if cond:
        print(f"  PASS  {label}  {extra}"); p += 1
    else:
        print(f"  FAIL  {label}  {extra}"); f += 1


def jwt_body(token: str) -> dict:
    body = token.split(".")[1]
    body += "=" * (-len(body) % 4)
    return json.loads(base64.urlsafe_b64decode(body))


async def main():
    print("=" * 74)
    print("AGENT STATE + AGENT KIND")
    print("=" * 74)

    svc = LivekitRoomServices(user_role="user", user_id=None)

    print("\n--- 1. token mein agent grant ---")

    agent_token = svc.livekit_token(
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
        room_name="state-test",
        user_name="agent",
    )
    claims = jwt_body(agent_token)
    video = claims.get("video", {})

    print(f"        agent grants: {video}")
    chk("agent token par agent=True", video.get("agent") is True,
        str(video.get("agent")))

    user_token = svc.livekit_token(
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
        room_name="state-test",
        user_name="parent",
    )
    uvideo = jwt_body(user_token).get("video", {})
    chk("aam user par agent grant NAHI",
        not uvideo.get("agent"), str(uvideo.get("agent")))

    print("\n--- 2. asli room: kind aur attribute ---")

    agent_room = rtc.Room()
    viewer_room = rtc.Room()

    seen = {"kind": None, "states": []}

    @viewer_room.on("participant_attributes_changed")
    def _on_attrs(changed, participant):
        if "lk.agent.state" in changed:
            seen["states"].append(changed["lk.agent.state"])

    try:
        await agent_room.connect(settings.LIVEKIT_URL, agent_token)
        await viewer_room.connect(settings.LIVEKIT_URL, user_token)
        await asyncio.sleep(2)

        # viewer ko agent kaise nazar aata hai
        for participant in viewer_room.remote_participants.values():
            if participant.identity == "agent":
                seen["kind"] = participant.kind

        # NOTE: token mein agent=True hone ke bawajood ye server
        # ParticipantKind AGENT nahi deta - wo kind sirf LiveKit
        # Agents framework ke zariye milta hai. Is liye frontend
        # ka useVoiceAssistant() hamare worker ko nahi dhoond
        # sakta, aur AgentVisualizer identity se dhoondta hai.
        # Yehi baat yahan naapi jati hai.
        agent_kind = rtc.ParticipantKind.PARTICIPANT_KIND_AGENT
        print(f"        viewer ko agent ka kind: {seen['kind']}"
              f"  (AGENT={agent_kind} - is server par nahi milta)")

        chk("agent identity se mil jata hai",
            seen["kind"] is not None,
            "<- AgentVisualizer isi par chalta hai")

        # ab wahi raasta jo pipeline use karti hai
        class Handle:
            room = agent_room
            _agent_state = None

        handle = Handle()

        for state in ("thinking", "speaking", "listening"):
            with contextlib.redirect_stdout(noise):
                await voice_pipeline.publish_agent_state(handle, state)
            await asyncio.sleep(1.2)

        print(f"        viewer ne suna: {seen['states']}")
        chk("teenon states pahunchin",
            seen["states"] == ["thinking", "speaking", "listening"],
            str(seen["states"]))

        # wahi state dobara bheji jaye to network par na jaye
        before = len(seen["states"])
        with contextlib.redirect_stdout(noise):
            await voice_pipeline.publish_agent_state(handle, "listening")
        await asyncio.sleep(1)
        chk("wahi state dobara nahi bheji jati",
            len(seen["states"]) == before,
            f"{before} -> {len(seen['states'])}")

    finally:
        with contextlib.suppress(Exception):
            await agent_room.disconnect()
        with contextlib.suppress(Exception):
            await viewer_room.disconnect()

    print("\n" + "=" * 74)
    print(f"  PASS: {p}   FAIL: {f}")
    print("=" * 74)


asyncio.run(main())
