"""
RAG knowledge base ka intezaam.

Pehle knowledge base update karne ka KOI raasta nahi tha. Ingestion ka
code maujood tha (ingestion.py + vectorstore.py) magar use sirf purana
livekit_Rag_services/main.py bulata tha - jo dead prototype tha aur
chalti hui service ka hissa nahi. Is liye data/text_files/ badalne se
kuch nahi hota tha.

Ye ops endpoints hain, aam users ke liye nahi - is liye JWT ke bajaye
X-Internal-Key se protect kiye gaye hain (wahi jo /users/internal par).
"""

import asyncio
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, status

from backend.microservices.livekit_Rag_services.services.rag_engine.ingestion import (
    assemble_knowledge_base,
)
from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
    get_index_stats,
    rebuild_vector_store,
)

router = APIRouter(prefix="/rag", tags=["RAG Knowledge Base"])


INTERNAL_KEY = os.getenv(
    "INTERNAL_SERVICE_KEY",
    "vocira-internal-dev-key-change-me",
)


# Ek waqt mein ek hi sync - do sath chalein to ek doosre ke vectors
# delete kar denge.
_sync_lock = asyncio.Lock()

_last_sync: dict = {
    "state": "never",       # never | running | success | failed
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}


def _check_key(key: str | None):
    if key != INTERNAL_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service key",
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _run_sync():
    """Background sync: files/URLs -> chunks -> embeddings -> Pinecone."""
    async with _sync_lock:
        _last_sync.update(
            state="running",
            started_at=_now(),
            finished_at=None,
            result=None,
            error=None,
        )

        try:
            print("📚 [RAG Sync] knowledge base assemble ho rahi hai...")
            chunks = await assemble_knowledge_base()

            if not chunks:
                raise RuntimeError(
                    "Koi content nahi mila - data/pdf, data/text_files "
                    "aur data/urls.txt check karein"
                )

            print(f"📚 [RAG Sync] {len(chunks)} chunks -> Pinecone")
            result = await rebuild_vector_store(chunks)

            # Kis file se kitne chunks bane - admin panel ye
            # dikhata hai. Pinecone se ye ginti poochna mehnga
            # hai, aur yahan wo pehle se haath mein hai.
            counts = {}
            for chunk in chunks:
                source = (chunk.metadata or {}).get("source")
                if source:
                    key = os.path.realpath(source) if os.path.exists(source) else source
                    counts[key] = counts.get(key, 0) + 1

            _last_sync["sources"] = counts

            _last_sync.update(
                state="success",
                finished_at=_now(),
                result=result,
            )
            print(f"✅ [RAG Sync] mukammal: {result}")

        except Exception as exc:
            _last_sync.update(
                state="failed",
                finished_at=_now(),
                error=f"{type(exc).__name__}: {exc}",
            )
            print(f"❌ [RAG Sync] fail: {exc}")


# ============================================================
# SYNC
# ============================================================

@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_knowledge_base(
    x_internal_key: str | None = Header(default=None),
):
    """
    Knowledge base dobara banayein.

    Background mein chalta hai - is liye foran 202 milta hai.
    Progress /rag/status se dekhein.
    """
    _check_key(x_internal_key)

    if _last_sync["state"] == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sync pehle se chal rahi hai",
        )

    asyncio.create_task(_run_sync())

    return {
        "state": "started",
        "message": "Sync background mein shuru ho gayi. /rag/status dekhein.",
    }


# ============================================================
# STATUS
# ============================================================

@router.get("/status")
async def knowledge_base_status(
    x_internal_key: str | None = Header(default=None),
):
    """Pinecone index ki halat aur aakhri sync ka nateeja."""
    _check_key(x_internal_key)

    try:
        stats = await get_index_stats()
    except Exception as exc:
        stats = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "index": stats,
        "last_sync": _last_sync,
    }
