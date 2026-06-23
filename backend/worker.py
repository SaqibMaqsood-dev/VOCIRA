import asyncio
from services.livekit.livekit_service import LivekitServices
from core.config  import settings
from core.rabitmq import RabbitMQ
import sys


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