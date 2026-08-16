import asyncio
import sys

from backend.services.livekit_Rag_serivces.core.config import settings
from backend.services.livekit_Rag_serivces.core.rabitmq import RabbitMQ
from backend.services.livekit_Rag_serivces.services.livekit.livekit_services.livekit_room_service import LivekitServices


async def main():
    print("Initializing Background Worker Service Engine...")
    
    rabbitmq = RabbitMQ()
    await rabbitmq.connect() 
    
    
    worker = LivekitServices(
        user_id=999, 
        user_role="audio_worker"
    )
    
    try:
        await rabbitmq.consumer(worker=worker)
    except KeyboardInterrupt:
        print("\nStopping background voice workers cleanly...")
    except Exception as e:
        print(f"System boot failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Standard entry point loop execution
    asyncio.run(main())

        # +92 318 9627289
        # +92 344 6887848
        # +92 319 9504300
        # +92 326 8679282
        # +92 307 4289452
        # +92 323 7186776    
        # +86 178 7567 8072
        # +92 329 0050778
        # +62 838-3450-9604
        # +1 (626) 604-6247
        # +92 305 4385305


