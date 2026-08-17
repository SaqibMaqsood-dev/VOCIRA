# Pinecone Vector Store
import time
import asyncio
import logging

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    PINECONE_API_KEY,
    INDEX_NAME,
    TEMP_INDEX_NAME,
    EMBEDDING_MODEL,
    EMBEDDING_DIM,
    TOP_K,
    PINECONE_NAMESPACE  # Imported namespace for data isolation
)

log = logging.getLogger(__name__)

# Embedding model will load for once and cached as well
_embeddings_instance = None


def get_embeddings():
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return _embeddings_instance


def wait_for_index(pc: Pinecone, index_name: str):
    """Wait until Pinecone index is ready. Sync function — always call via to_thread."""
    while not pc.describe_index(index_name).status["ready"]:
        time.sleep(1)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def upload_to_pinecone(chunks, embeddings, index_name: str):
    """Upload chunks to Pinecone with automatic retry and namespace isolation."""
    return PineconeVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        index_name=index_name,
        namespace=PINECONE_NAMESPACE  # Isolating chunks to your specific namespace
    )


def _build_vector_store_sync(chunks):
    """Fully synchronous. Only ever called via asyncio.to_thread — never call
    this directly from async code, it will block the event loop.

    Safe swap pattern: TEMP index poori tarah build aur verify hone tak
    production index (INDEX_NAME) ko chhua tak nahi jata, isliye live
    /ask traffic ke liye koi outage window nahi banta."""
    log.info("Initializing embedding model...")
    embeddings = get_embeddings()
    pc         = Pinecone(api_key=PINECONE_API_KEY)
    index_spec = ServerlessSpec(cloud="aws", region="us-east-1")

    if INDEX_NAME not in pc.list_indexes().names():
        log.info(f"Creating new production index: {INDEX_NAME}")
        pc.create_index(name=INDEX_NAME, dimension=EMBEDDING_DIM, metric="cosine", spec=index_spec)
        wait_for_index(pc, INDEX_NAME)
        upload_to_pinecone(chunks, embeddings, INDEX_NAME)
        return INDEX_NAME

    log.info("Existing index found. Building staging index (zero downtime)...")

    if TEMP_INDEX_NAME in pc.list_indexes().names():
        # Remove any leftover temporary index from a previous crashed run
        pc.delete_index(TEMP_INDEX_NAME)
        time.sleep(2)

    pc.create_index(name=TEMP_INDEX_NAME, dimension=EMBEDDING_DIM, metric="cosine", spec=index_spec)
    wait_for_index(pc, TEMP_INDEX_NAME)
    # Create a new staging index for the fresh data upload
    log.info(f"Uploading {len(chunks)} chunks to staging index...")
    upload_to_pinecone(chunks, embeddings, TEMP_INDEX_NAME)

    stats = pc.Index(TEMP_INDEX_NAME).describe_index_stats()
    if stats.get("total_vector_count", 0) == 0:
        pc.delete_index(TEMP_INDEX_NAME)
        raise RuntimeError("Staging index upload verification failed — aborting swap, production untouched.")
    # verify that the vectors have actually been uploaded to staging.
    log.info(f"Staging index verified with {stats.get('total_vector_count')} vectors. Swap ready.")
    log.info(f"Pinecone synced — {len(chunks)} chunks indexed in namespace '{PINECONE_NAMESPACE}'.")

    # Old index remains active serving live traffic until the new retriever
    # binds to the temp index, after which the old index is safely deleted.
    return TEMP_INDEX_NAME


async def build_vector_store(chunks):
    """Async wrapper — saara blocking Pinecone/embedding kaam thread mein
    offload karta hai, event loop kabhi block nahi hota.

    Returns: index name (string) jispe naya data ready hai — isko
    connect_existing_store(index_name=...) mein pass karo."""
    result_index_name = await asyncio.to_thread(_build_vector_store_sync, chunks)
    return result_index_name


def connect_existing_store(index_name: str = None):
    """Connect efficiently to an existing Pinecone index. Pass index_name
    explicitly after a sync to bind to the freshly built index
    (ho sakta hai INDEX_NAME ho ya TEMP_INDEX_NAME, jo bhi abhi live hai)."""
    target = index_name or INDEX_NAME
    embeddings = get_embeddings()
    pc         = Pinecone(api_key=PINECONE_API_KEY)

    if target in pc.list_indexes().names():
        store = PineconeVectorStore.from_existing_index(
            index_name=target,
            embedding=embeddings,
            namespace=PINECONE_NAMESPACE
        )
        retriever = store.as_retriever(search_kwargs={
            "k": TOP_K,
            "namespace": PINECONE_NAMESPACE  # Forces search query boundary isolation
        })
        return store, retriever

    return None, None