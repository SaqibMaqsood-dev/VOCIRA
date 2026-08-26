import asyncio, logging
from rag_engine.ingestion import assemble_knowledge_base
logging.basicConfig(level=logging.INFO)

async def main():
    chunks = await assemble_knowledge_base()
    print(f"\n=== TOTAL CHUNKS: {len(chunks)} ===\n")

asyncio.run(main())