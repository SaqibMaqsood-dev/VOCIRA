from rag_engine.vectorstore import connect_existing_store
from rag_engine.config import INDEX_NAME

store, retriever = connect_existing_store(INDEX_NAME)
docs = retriever.invoke("swimming pool")

print(f"Retrieved {len(docs)} docs:\n")
for d in docs:
    print("-", d.page_content[:300])
    print("  source:", d.metadata.get("source"))
    print()