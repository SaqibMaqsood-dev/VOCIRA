"""
Standalone test for rag_engine/query.py's ask_vocira() — the fixed version
with clean_for_tts() applied. Run this as a module from the project root to
check in plain text whether markdown (asterisks, numbered lists) is being
stripped before the answer would go to TTS.

Usage:
    cd D:\\vocira_backend
    D:\\vocira_backend\\rag_engine\\.venv\\Scripts\\Activate.ps1
    python -m rag_engine.test_query
"""

import asyncio
from rag_engine.vectorstore import connect_existing_store
from rag_engine.config import INDEX_NAME
from rag_engine.query import ask_vocira


async def main():
    print("Connecting to existing Pinecone index...")
    _, retriever = connect_existing_store(INDEX_NAME)
    if retriever is None:
        print(f"Index '{INDEX_NAME}' not found in Pinecone. Aborting.")
        return
    print("Connected. Retriever ready.\n")

    while True:
        query = input("Ask a question (or 'quit' to exit): ").strip()
        if query.lower() in ("quit", "exit"):
            break
        if not query:
            continue

        answer = await ask_vocira(retriever, query)
        print("\n--- ANSWER (post clean_for_tts) ---")
        print(answer)
        print("--- END ---\n")


if __name__ == "__main__":
    asyncio.run(main())