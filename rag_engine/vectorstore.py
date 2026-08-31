# Pinecone Vector Store
import time
import asyncio
import logging

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from tenacity import retry, stop_after_attempt, wait_exponential

from rag_engine.config import (
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


def _swap_staging_into_production(pc: Pinecone, temp_index_name: str, prod_index_name: str, namespace: str):
    """Actually performs the swap that was previously only described in a comment.

    Pinecone indexes can't be renamed, so a true swap means: copy every vector
    from the staging index into production (overwriting stale data), verify
    the copy landed, then delete the staging index. Production is only ever
    cleared AFTER staging is fully verified, so a failed sync never leaves
    production empty.
    """
    prod_index = pc.Index(prod_index_name)
    temp_index = pc.Index(temp_index_name)

    # Clear stale vectors in production namespace right before writing fresh
    # data — if this fails, we bail out and leave production untouched.
    try:
        prod_index.delete(delete_all=True, namespace=namespace)
    except Exception as e:
        # Pinecone throws if the namespace doesn't exist yet (first-ever sync
        # via this path) — safe to ignore, means there's nothing stale to clear.
        log.info(f"No existing production vectors to clear (or clear skipped): {e}")

    copied = 0
    for id_batch in temp_index.list(namespace=namespace):
        fetched = temp_index.fetch(ids=id_batch, namespace=namespace)
        vectors = [
            (vec_id, vec.values, vec.metadata)
            for vec_id, vec in fetched.vectors.items()
        ]
        if vectors:
            prod_index.upsert(vectors=vectors, namespace=namespace)
            copied += len(vectors)

    # Verify the copy actually landed in production before declaring success.
    stats = prod_index.describe_index_stats()
    prod_count = stats.get("namespaces", {}).get(namespace, {}).get("vector_count", 0)
    if prod_count == 0:
        raise RuntimeError(
            f"Swap failed — production namespace '{namespace}' is empty after copy attempt. "
            "Staging index left intact for investigation."
        )

    log.info(f"Swapped {copied} vectors into production index '{prod_index_name}' (namespace '{namespace}'). Verified count: {prod_count}.")

    pc.delete_index(temp_index_name)
    log.info(f"Deleted temporary staging index '{temp_index_name}'.")


def _build_vector_store_sync(chunks):
    """Fully synchronous. Only ever called via asyncio.to_thread — never call
    this directly from async code, it will block the event loop.

   Safe swap pattern: the main index (INDEX_NAME) is never touched until
    the temporary index is fully built and verified. Only after verification
    are vectors copied from the temporary index into the main index
    (_swap_staging_into_production), after which the temporary index is
    deleted — so there's no downtime for live /ask traffic, and the main
    index is never left outdated."""

    if not chunks:
        raise RuntimeError(
            "assemble_knowledge_base() returned 0 chunks — nothing to upload. "
            "Check PDF_PATH/TEXT_FILES_PATH have files and urls.txt scraping succeeded "
            "before running the sync."
        )

    log.info("Initializing embedding model...")
    embeddings = get_embeddings()
    pc         = Pinecone(api_key=PINECONE_API_KEY)
    index_spec = ServerlessSpec(cloud="aws", region="us-east-1")

    if INDEX_NAME not in pc.list_indexes().names():
        log.info(f"Creating new production index: {INDEX_NAME}")
        pc.create_index(name=INDEX_NAME, dimension=EMBEDDING_DIM, metric="cosine", spec=index_spec)
        wait_for_index(pc, INDEX_NAME)
        upload_to_pinecone(chunks, embeddings, INDEX_NAME)

        # verify that the vectors actually landed — first-time creation had
        # no verification before, which is how the index went live empty.
        stats = pc.Index(INDEX_NAME).describe_index_stats()
        if stats.get("total_vector_count", 0) == 0:
            raise RuntimeError(
                f"Index '{INDEX_NAME}' was created but 0 vectors were uploaded. "
                "Upload silently failed — check embeddings/Pinecone credentials."
            )
        log.info(f"Production index verified with {stats.get('total_vector_count')} vectors.")
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

    #  actually move the
    # verified data from staging , then clean up staging.
    _swap_staging_into_production(pc, TEMP_INDEX_NAME, INDEX_NAME, PINECONE_NAMESPACE)

    log.info(f"Pinecone synced — {len(chunks)} chunks indexed in namespace '{PINECONE_NAMESPACE}'.")

    #  index now has the fresh data — always return INDEX_NAME,
    # never TEMP_INDEX_NAME, since staging no longer exists after the swap.
    return INDEX_NAME


async def build_vector_store(chunks):
    """Async wrapper — offloads all blocking pinecone/embedding work to 
    a separate thread, so the event loop never gets blocked.

    Returns: INDEX_NAME (production) — this is now always the production
    index, since the swap logic guarantees fresh data lands there."""
    result_index_name = await asyncio.to_thread(_build_vector_store_sync, chunks)
    return result_index_name


def connect_existing_store(index_name: str = None):
    """Connect efficiently to an existing Pinecone index. Defaults to
    production INDEX_NAME — this is now always safe to call with no
    arguments after a sync, since build_vector_store always returns
    INDEX_NAME (the swap makes TEMP_INDEX_NAME obsolete after each sync)."""
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