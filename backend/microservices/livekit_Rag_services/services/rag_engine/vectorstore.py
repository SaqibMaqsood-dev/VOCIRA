"""
Pinecone vector store.

NOTE — purana "safe swap" hata diya gaya hai.

Pehle build_vector_store() TEMP index banati thi, us mein upload karti
thi, verify karti thi... aur TEMP ka naam laut kar khatam ho jati thi.
Temp se production mein swap ka code kahin tha hi nahi, jabke retriever
production index padhta hai. Yaani wo raasta chal bhi jata to knowledge
base kabhi update na hota.

Ab seedha tareeqa: namespace khali karo, naye chunks daalo. Chhoti
knowledge base ke liye ye chand second ka kaam hai.
"""

import asyncio
import logging
import time

from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    PINECONE_API_KEY,
    INDEX_NAME,
    EMBEDDING_MODEL,
    EMBEDDING_DIM,
    EMBEDDING_PROVIDER,
    GEMINI_API_KEY,
    GEMINI_EMBEDDING_MODEL,
    GEMINI_EMBEDDING_DIM,
    LOCAL_EMBEDDING_MODEL,
    TOP_K,
    PINECONE_NAMESPACE,
)
from backend.microservices.livekit_Rag_services.services.rag_engine.embeddings import (
    build_embeddings,
)

log = logging.getLogger(__name__)

_embeddings_instance = None


def get_embeddings():
    """Config ke mutabiq embeddings (local ya Gemini). Ek hi baar banta hai."""
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = build_embeddings(
            EMBEDDING_PROVIDER,
            local_model=LOCAL_EMBEDDING_MODEL,
            gemini_api_key=GEMINI_API_KEY,
            gemini_model=GEMINI_EMBEDDING_MODEL,
            gemini_dimensions=GEMINI_EMBEDDING_DIM,
        )
    return _embeddings_instance


def _client() -> Pinecone:
    return Pinecone(api_key=PINECONE_API_KEY)


def wait_for_index(pc: Pinecone, index_name: str, timeout: int = 120):
    """Index ke ready hone ka intezaar. Sync — hamesha to_thread se bulayein."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pc.describe_index(index_name).status["ready"]:
            return
        time.sleep(1)
    raise RuntimeError(f"Index '{index_name}' {timeout}s mein ready nahi hui")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def upload_to_pinecone(chunks, embeddings, index_name: str):
    return PineconeVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        index_name=index_name,
        namespace=PINECONE_NAMESPACE,
    )


def _rebuild_sync(chunks) -> dict:
    """Poori tarah synchronous — sirf asyncio.to_thread se bulayein."""
    pc = _client()
    existing = pc.list_indexes().names()

    # ---- index maujood na ho to bana dein ----
    if INDEX_NAME not in existing:
        log.info("Index '%s' bana rahe hain (dim=%s)", INDEX_NAME, EMBEDDING_DIM)
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        wait_for_index(pc, INDEX_NAME)
    else:
        # dimension mismatch pakrein - Gemini/OpenAI embeddings par
        # jate waqt yahi sab se aam ghalti hoti hai
        dim = pc.describe_index(INDEX_NAME).dimension
        if dim != EMBEDDING_DIM:
            raise RuntimeError(
                f"Index '{INDEX_NAME}' ki dimension {dim} hai magar "
                f"embedding model {EMBEDDING_DIM} deta hai. Nayi index "
                f"banayein ya purani delete karein."
            )

    index = pc.Index(INDEX_NAME)

    # ---- purane vectors hatayein (namespace ke andar) ----
    before = (
        index.describe_index_stats()
        .get("namespaces", {})
        .get(PINECONE_NAMESPACE, {})
        .get("vector_count", 0)
    )
    if before:
        log.info("Namespace '%s' se %s purane vectors hata rahe hain",
                 PINECONE_NAMESPACE, before)
        try:
            index.delete(delete_all=True, namespace=PINECONE_NAMESPACE)
            time.sleep(2)
        except Exception as exc:
            # namespace na ho to Pinecone 404 deta hai - koi masla nahi
            log.warning("Namespace delete: %s", exc)

    # ---- naye chunks ----
    log.info("Uploading %s chunks...", len(chunks))
    upload_to_pinecone(chunks, get_embeddings(), INDEX_NAME)

    # Pinecone ka index thori der baad consistent hota hai
    after = 0
    for _ in range(15):
        time.sleep(2)
        after = (
            index.describe_index_stats()
            .get("namespaces", {})
            .get(PINECONE_NAMESPACE, {})
            .get("vector_count", 0)
        )
        if after >= len(chunks):
            break

    return {
        "index": INDEX_NAME,
        "namespace": PINECONE_NAMESPACE,
        "dimension": EMBEDDING_DIM,
        "chunks_uploaded": len(chunks),
        "vectors_before": before,
        "vectors_after": after,
    }


async def rebuild_vector_store(chunks) -> dict:
    """Namespace khali karke naye chunks daalein. Result ka summary."""
    return await asyncio.to_thread(_rebuild_sync, chunks)


# purana naam bhi chalta rahe
build_vector_store = rebuild_vector_store


def _stats_sync() -> dict:
    pc = _client()
    names = pc.list_indexes().names()

    if INDEX_NAME not in names:
        return {
            "index": INDEX_NAME,
            "exists": False,
            "vectors": 0,
            "namespace": PINECONE_NAMESPACE,
            "embedding_model": EMBEDDING_MODEL,
            "dimension": EMBEDDING_DIM,
            "top_k": TOP_K,
        }

    d = pc.describe_index(INDEX_NAME)
    s = pc.Index(INDEX_NAME).describe_index_stats()
    ns = s.get("namespaces", {})

    return {
        "index": INDEX_NAME,
        "exists": True,
        "index_dimension": d.dimension,
        "metric": d.metric,
        "namespace": PINECONE_NAMESPACE,
        "vectors": ns.get(PINECONE_NAMESPACE, {}).get("vector_count", 0),
        "vectors_all_namespaces": s.get("total_vector_count", 0),
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimension": EMBEDDING_DIM,
        "dimension_match": d.dimension == EMBEDDING_DIM,
        "top_k": TOP_K,
    }


async def get_index_stats() -> dict:
    """Pinecone index ki maujooda halat."""
    return await asyncio.to_thread(_stats_sync)


def connect_existing_store(index_name: str = None):
    """Maujooda index se retriever banayein."""
    target = index_name or INDEX_NAME
    pc = _client()

    if target in pc.list_indexes().names():
        store = PineconeVectorStore.from_existing_index(
            index_name=target,
            embedding=get_embeddings(),
            namespace=PINECONE_NAMESPACE,
        )
        retriever = store.as_retriever(
            search_kwargs={"k": TOP_K, "namespace": PINECONE_NAMESPACE}
        )
        log.info("Pinecone '%s' se juda (namespace '%s')", target, PINECONE_NAMESPACE)
        return retriever

    log.error("Index '%s' Pinecone par nahi mili", target)
    return None
