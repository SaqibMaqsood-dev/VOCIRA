"""
Agent worker.

Listens for "session.created" on RabbitMQ and sends the AI agent
into a LiveKit room for each call.

ONE LivekitRoomServices used to be built here and used for every
call. That object holds per-call state - room, _speech_generation,
_is_agent_speaking, agent_source - so two concurrent calls corrupted
each other's state.

A fresh instance is now built for each call (through a factory), and
each call runs in its own asyncio task.
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
    """A fresh instance for every call."""
    return LivekitRoomServices(
        user_id=None,
        user_role="worker",
    )


async def main() -> None:
    print("=" * 60)
    print("VOCIRA agent worker")
    print(f"   concurrent calls  : {MAX_CONCURRENT_CALLS}")
    print(f"   call ki max lambai : {MAX_CALL_SECONDS}s")
    print("=" * 60)

    rabbitmq = RabbitMQ()

    await rabbitmq.consumer(make_worker)


if __name__ == "__main__":
    asyncio.run(main())
