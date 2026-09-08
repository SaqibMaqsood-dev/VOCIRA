"""
Agent worker.

RabbitMQ se "session.created" sunta hai aur har call ke liye AI agent
ko LiveKit room mein bhejta hai.

Pehle yahan EK LivekitRoomServices banaya jata tha aur wahi sab calls
ke liye use hota tha. Us object par per-call state hoti hai - room,
_speech_generation, _is_agent_speaking, agent_source - is liye do
calls sath chalne par ek doosre ki state kharab kar deti.

Ab har call ke liye naya instance banta hai (factory ke zariye), aur
har call apne asyncio task mein chalti hai.
"""

import asyncio

from backend.microservices.livekit_Rag_services.core.rabitmq import (
    MAX_CALL_SECONDS,
    MAX_CONCURRENT_CALLS,
    RabbitMQ,
)
from backend.microservices.livekit_Rag_services.services.livekit.livekit_services.livekit_room_service import (
    LivekitRoomServices,
)


def make_worker() -> LivekitRoomServices:
    """Har call ke liye taza instance."""
    return LivekitRoomServices(
        user_id=None,
        user_role="worker",
    )


async def main() -> None:
    print("=" * 60)
    print("🎧 VOCIRA agent worker")
    print(f"   concurrent calls  : {MAX_CONCURRENT_CALLS}")
    print(f"   call ki max lambai : {MAX_CALL_SECONDS}s")
    print("=" * 60)

    rabbitmq = RabbitMQ()

    await rabbitmq.consumer(make_worker)


if __name__ == "__main__":
    asyncio.run(main())
