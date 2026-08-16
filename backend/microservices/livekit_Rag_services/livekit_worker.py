import asyncio

from backend.microservices.livekit_Rag_services.services.livekit.livekit_services.livekit_room_service import (
    LivekitRoomServices,
)
from backend.microservices.livekit_Rag_services.core.rabitmq import RabbitMQ

async def main() -> None:

    worker = LivekitRoomServices(
        user_id=None,
        user_role="worker",
    )

    rabbitmq = RabbitMQ()

    await rabbitmq.consumer(worker)
    print("=========consumer is working =========")

if __name__ == "__main__":
    asyncio.run(main())