import asyncio

from backend.microservices.livekit_Rag_services.services.livekit.livekit_services.livekit_room_service import (
    LivekitRoomServices,
)

from backend.microservices.livekit_Rag_services.core.rabitmq import (
    RabbitMQ,
)


def create_livekit_worker(
    user_id,
    user_role,
):
    """
    Factory used by RabbitMQ to create a fresh
    LivekitRoomServices instance for every session.
    """

    return LivekitRoomServices(
        user_id=user_id,
        user_role=user_role,
    )


async def main() -> None:

    print("=" * 70)
    print("🚀 VOCIRA LIVEKIT BACKGROUND WORKER")
    print("=" * 70)

    rabbitmq = RabbitMQ()

    try:

        await rabbitmq.connect()

        print("✅ RabbitMQ connected")
        print("🎧 Waiting for session.created events...")


        await rabbitmq.consumer(
            create_livekit_worker
        )

    except KeyboardInterrupt:

        print("\n🛑 Worker stopped by user.")

    except Exception as e:

        print(
            f"❌ Worker failed: {e}"
        )

        raise

    finally:

        if rabbitmq._connection:

            await rabbitmq._connection.close()

            print(
                "🔌 RabbitMQ connection closed"
            )


if __name__ == "__main__":

    asyncio.run(main())
