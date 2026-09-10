"""
RAG knowledge base ka intezaam.

There used to be NO way to update the knowledge base. The ingestion
code existed (ingestion.py + vectorstore.py) but was only called by
the old livekit_Rag_services/main.py - a dead prototype that is not
part of the running service. So changing data/text_files/ did nothing.

These are ops endpoints, not for ordinary users - so they are guarded
by X-Internal-Key rather than JWT (the same one /users/internal uses).
"""

import asyncio
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, status

from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    DATA_DIR,
)
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


# One sync at a time - two running together would delete each
# other's vectors.
_sync_lock = asyncio.Lock()

_last_sync: dict = {
    "state": "never",       # never | running | success | failed
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}

# The sync result is written to disk as well.
#
# It lived only in memory before, so a service restart turned it into
# "never" - even though the data was sitting in Pinecone. The admin
# panel then showed "not indexed" against every file and the user ran
# another sync for nothing.
_STATE_FILE = os.path.join(
    os.path.dirname(DATA_DIR), "data", ".sync_state.json"
)


def _save_state() -> None:
    """This is a notification, not real work - just log a failure."""
    try:
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        with open(_STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(_last_sync, handle)
    except Exception as error:
        print(f"[RAG Sync] could not save state: {error}")


def _load_state() -> None:
    """Restore the previous state when the service starts."""
    try:
        if not os.path.isfile(_STATE_FILE):
            return

        with open(_STATE_FILE, encoding="utf-8") as handle:
            saved = json.load(handle)

        if isinstance(saved, dict):
            # "running" cannot be trusted: if the service died while
            # a sync was in progress, that sync is not running
            # anywhere now.
            if saved.get("state") == "running":
                saved["state"] = "failed"
                saved["error"] = "Service restarted while syncing"

            _last_sync.update(saved)

    except Exception as error:
        print(f"[RAG Sync] could not read the saved state: {error}")


_load_state()


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
            print("[RAG Sync] assembling the knowledge base...")
            chunks = await assemble_knowledge_base()

            if not chunks:
                raise RuntimeError(
                    "No content found — check data/pdf, data/text_files "
                    "and data/urls.txt"
                )

            print(f"[RAG Sync] {len(chunks)} chunks -> Pinecone")
            result = await rebuild_vector_store(chunks)

            # How many chunks came from each file - the admin panel
            # displays this. Asking Pinecone for the counts is
            # expensive, and here they are already at hand.
            counts = {}
            for chunk in chunks:
                source = (chunk.metadata or {}).get("source")
                if source:
                    key = os.path.realpath(source) if os.path.exists(source) else source
                    counts[key] = counts.get(key, 0) + 1

            _last_sync["sources"] = counts
            _save_state()

            _last_sync.update(
                state="success",
                finished_at=_now(),
                result=result,
            )
            _save_state()
            print(f"[RAG Sync] done: {result}")

        except Exception as exc:
            _last_sync.update(
                state="failed",
                finished_at=_now(),
                error=f"{type(exc).__name__}: {exc}",
            )
            _save_state()
            print(f"[RAG Sync] fail: {exc}")


# ============================================================
# SYNC
# ============================================================

@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_knowledge_base(
    x_internal_key: str | None = Header(default=None),
):
    """
    Knowledge base dobara banayein.

    Runs in the background - so a 202 comes back immediately.
    Progress /rag/status se dekhein.
    """
    _check_key(x_internal_key)

    if _last_sync["state"] == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A sync is already running.",
        )

    asyncio.create_task(_run_sync())

    return {
        "state": "started",
        "message": "Sync started in the background. Check /rag/status.",
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
