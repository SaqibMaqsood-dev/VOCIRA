import asyncio
from core.config import settings
from services.livekit.livekit_room_service import LivekitServices

# This worker should be run in its own terminal.
# It connects to LiveKit and stays alive to print participant events.

async def main() -> None:
    worker = LivekitServices(user_id=0, user_name='worker')
    token = worker.livekit_token(
        api_key=settings.API_KEY,
        api_secret=settings.API_SECRET,
        room_name='vocira-room'
    )

    await worker.connect_worker(token=token)


if __name__ == '__main__':
    asyncio.run(main())
