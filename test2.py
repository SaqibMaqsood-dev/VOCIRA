import asyncio, logging
from rag_engine.ingestion import assemble_knowledge_base
from rag_engine.vectorstore import build_vector_store

logging.basicConfig(level=logging.INFO)

async def main():
    chunks = await assemble_knowledge_base()
    print(f"Got {len(chunks)} chunks, syncing to Pinecone...")
    index_name = await build_vector_store(chunks)
    print(f"\n=== SYNCED TO INDEX: {index_name} ===\n")

asyncio.run(main())