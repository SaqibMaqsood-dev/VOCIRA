import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from services.livekit.livekit_room_service import LivekitServices
from core.config import settings
from core.rabitmq import RabbitMQ

import rag_engine.state as rag_state
from rag_engine.vectorstore import connect_existing_store
from rag_engine.config import INDEX_NAME


async def main():
    print("Initializing Background Worker Service Engine...")

    # ── RAG knowledge base connect ──
    store, retriever = connect_existing_store(index_name=INDEX_NAME)
    if retriever:
        rag_state.vector_store = store
        rag_state.retriever = retriever
        print("✅ RAG knowledge base connected.")
    else:
        print("⚠️ RAG index not found — voice pipeline general conversation pe fallback karega.")

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
    asyncio.run(main())