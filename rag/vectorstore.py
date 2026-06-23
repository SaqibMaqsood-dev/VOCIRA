#Pinecone
import time
import logging

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from tenacity import retry, stop_after_attempt, wait_exponential

from rag.config import (
    PINECONE_API_KEY,
    INDEX_NAME,
    TEMP_INDEX_NAME,
    EMBEDDING_MODEL,
    EMBEDDING_DIM,
    TOP_K
)

log = logging.getLogger(__name__)


def get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def wait_for_index(pc: Pinecone, index_name: str):
    """Wait until Pinecone index is ready."""
    while not pc.describe_index(index_name).status["ready"]:
        time.sleep(1)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def upload_to_pinecone(chunks, embeddings, index_name: str):
    """Upload chunks to Pinecone with automatic retry."""
    return PineconeVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        index_name=index_name
    )


async def build_vector_store(chunks):
    """Safe swap pattern — upload first, delete old after confirmation."""
    log.info("Initializing embedding model...")
    embeddings = get_embeddings()
    pc         = Pinecone(api_key=PINECONE_API_KEY)
    index_spec = ServerlessSpec(cloud="aws", region="us-east-1")

    if INDEX_NAME not in pc.list_indexes().names():
        log.info(f"Creating new production index: {INDEX_NAME}")
        pc.create_index(name=INDEX_NAME, dimension=EMBEDDING_DIM, metric="cosine", spec=index_spec)
        wait_for_index(pc, INDEX_NAME)
        store = upload_to_pinecone(chunks, embeddings, INDEX_NAME)

    else:
        log.info("Existing index found. Starting safe swap...")

        if TEMP_INDEX_NAME not in pc.list_indexes().names():
            pc.create_index(name=TEMP_INDEX_NAME, dimension=EMBEDDING_DIM, metric="cosine", spec=index_spec)
            wait_for_index(pc, TEMP_INDEX_NAME)

        log.info(f"Uploading {len(chunks)} chunks to staging index...")
        upload_to_pinecone(chunks, embeddings, TEMP_INDEX_NAME)
        log.info("Staging upload confirmed. Replacing production index...")

        pc.delete_index(INDEX_NAME)
        time.sleep(3)

        pc.create_index(name=INDEX_NAME, dimension=EMBEDDING_DIM, metric="cosine", spec=index_spec)
        wait_for_index(pc, INDEX_NAME)

        store = upload_to_pinecone(chunks, embeddings, INDEX_NAME)
        pc.delete_index(TEMP_INDEX_NAME)
        log.info("Staging index cleaned up.")

    log.info(f"Pinecone synced — {len(chunks)} chunks indexed.")
    return store


def connect_existing_store():
    """Connect to existing Pinecone index on startup."""
    embeddings = get_embeddings()
    pc         = Pinecone(api_key=PINECONE_API_KEY)

    if INDEX_NAME in pc.list_indexes().names():
        store     = PineconeVectorStore(index_name=INDEX_NAME, embedding=embeddings)
        retriever = store.as_retriever(search_kwargs={"k": TOP_K})
        return store, retriever

    return None, None