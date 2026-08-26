import asyncio
from rag_engine.vectorstore import connect_existing_store
from rag_engine.config import INDEX_NAME
from rag_engine.query import ask_vocira

async def main():
    store, retriever = connect_existing_store(INDEX_NAME)

    queries = [
        "admission ke liye kya karna hota hai",
        "school ka fee structure kya hai",
        "kya aapke paas swimming pool hai",
    ]

    for q in queries:
        answer = await ask_vocira(retriever, q)
        print(f"\nQ: {q}")
        print(f"A ({len(answer.split())} words): {answer}")
        print("-" * 60)

asyncio.run(main())
