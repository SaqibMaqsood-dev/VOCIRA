from rag_engine.vectorstore import connect_existing_store
from rag_engine.config import INDEX_NAME

store, retriever = connect_existing_store(INDEX_NAME)  # explicitly production index

if retriever is None:
    print("Retriever is None — connection failed")
else:
    docs = retriever.invoke("admission process")
    print(f"\nRetrieved {len(docs)} docs from PRODUCTION index ({INDEX_NAME}):\n")
    for d in docs:
        print("-", d.page_content[:150])
        print("  source:", d.metadata.get("source"))
        print()