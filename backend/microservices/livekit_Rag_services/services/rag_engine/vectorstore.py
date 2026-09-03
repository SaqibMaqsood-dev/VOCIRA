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
    PINECONE_NAMESPACE
)

log = logging.getLogger(__name__)

# Embedding model cached globally
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
        namespace=PINECONE_NAMESPACE
    )


def _build_vector_store_sync(chunks):
    """Fully synchronous. Only ever called via asyncio.to_thread."""
    log.info("Initializing embedding model...")
    embeddings = get_embeddings()
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index_spec = ServerlessSpec(cloud="aws", region="us-east-1")

    if INDEX_NAME not in pc.list_indexes().names():
        log.info(f"Creating new production index: {INDEX_NAME}")
        pc.create_index(name=INDEX_NAME, dimension=EMBEDDING_DIM, metric="cosine", spec=index_spec)
        wait_for_index(pc, INDEX_NAME)
        upload_to_pinecone(chunks, embeddings, INDEX_NAME)
        return INDEX_NAME

    log.info("Existing index found. Building staging index (zero downtime)...")

    if TEMP_INDEX_NAME in pc.list_indexes().names():
        pc.delete_index(TEMP_INDEX_NAME)
        time.sleep(2)

    pc.create_index(name=TEMP_INDEX_NAME, dimension=EMBEDDING_DIM, metric="cosine", spec=index_spec)
    wait_for_index(pc, TEMP_INDEX_NAME)
    log.info(f"Uploading {len(chunks)} chunks to staging index...")
    upload_to_pinecone(chunks, embeddings, TEMP_INDEX_NAME)

    stats = pc.Index(TEMP_INDEX_NAME).describe_index_stats()
    if stats.get("total_vector_count", 0) == 0:
        pc.delete_index(TEMP_INDEX_NAME)
        raise RuntimeError("Staging index upload verification failed — aborting swap.")

    log.info(f"Staging index verified with {stats.get('total_vector_count')} vectors.")
    return TEMP_INDEX_NAME


async def build_vector_store(chunks):
    """Async wrapper — offloads blocking Pinecone/embedding work to a thread."""
    result_index_name = await asyncio.to_thread(_build_vector_store_sync, chunks)
    return result_index_name


def connect_existing_store(index_name: str = None):
    """Connect to an existing Pinecone index and return a retriever only."""
    target = index_name or INDEX_NAME
    embeddings = get_embeddings()
    pc = Pinecone(api_key=PINECONE_API_KEY)

    if target in pc.list_indexes().names():
        store = PineconeVectorStore.from_existing_index(
            index_name=target,
            embedding=embeddings,
            namespace=PINECONE_NAMESPACE
        )
        retriever = store.as_retriever(search_kwargs={
            "k": TOP_K,
            "namespace": PINECONE_NAMESPACE
        })
        log.info(f"Connected to Pinecone index '{target}' with namespace '{PINECONE_NAMESPACE}'.")
        return retriever   # 🔥 return only retriever now

    log.error(f"Index '{target}' not found in Pinecone.")
    return None
