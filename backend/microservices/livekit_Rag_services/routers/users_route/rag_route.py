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
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, status

from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    DATA_DIR,
)
from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
    get_index_stats,
    rebuild_vector_store,
)
from backend.microservices.livekit_Rag_services.services import tenants

# NOTE: ingestion is imported inside _run_sync(), not here. It pulls
# in langchain's text splitters, which drag in sentence_transformers
# and torch - about 7 of the ~10 seconds this service spent importing
# before it could answer anything. A sync runs rarely; every boot paid
# for it. Loading it at first sync moves that cost off the startup
# path (embeddings come from Gemini, so torch is never used anyway).

router = APIRouter(prefix="/rag", tags=["RAG Knowledge Base"])


INTERNAL_KEY = os.getenv(
    "INTERNAL_SERVICE_KEY",
    "vocira-internal-dev-key-change-me",
)


# One sync at a time - two running together would delete each
# other's vectors.
_sync_lock = asyncio.Lock()

def _fresh_state() -> dict:
    return {
        "state": "never",       # never | running | success | failed
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }


# One sync state per school - each school's knowledge is synced into
# its own namespace, on its own. _last_sync stays the first school's,
# so everything that already reads it keeps working.
_sync_states: dict = {school_id: _fresh_state() for school_id in tenants.SCHOOLS}
_last_sync: dict = _sync_states[tenants.DEFAULT_SCHOOL_ID]


def sync_state(school_id: str | None = None) -> dict:
    return _sync_states[tenants.get_school(school_id).id]

# The sync result is written to disk as well.
#
# It lived only in memory before, so a service restart turned it into
# "never" - even though the data was sitting in Pinecone. The admin
# panel then showed "not indexed" against every file and the user ran
# another sync for nothing.
_STATE_FILE = os.path.join(
    os.path.dirname(DATA_DIR), "data", ".sync_state.json"
)


def _state_file(school_id: str) -> str:
    # The first school keeps the file it always had.
    if school_id == tenants.DEFAULT_SCHOOL_ID:
        return _STATE_FILE
    return os.path.join(os.path.dirname(_STATE_FILE), f".sync_state.{school_id}.json")


def _save_state(school_id: str = tenants.DEFAULT_SCHOOL_ID) -> None:
    """This is a notification, not real work - just log a failure."""
    try:
        path = _state_file(school_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(_sync_states[school_id], handle)
    except Exception as error:
        print(f"[RAG Sync] could not save state: {error}")


def _load_state(school_id: str = tenants.DEFAULT_SCHOOL_ID) -> None:
    """Restore the previous state when the service starts."""
    try:
        path = _state_file(school_id)
        if not os.path.isfile(path):
            return

        with open(path, encoding="utf-8") as handle:
            saved = json.load(handle)

        if isinstance(saved, dict):
            # "running" cannot be trusted: if the service died while
            # a sync was in progress, that sync is not running
            # anywhere now.
            if saved.get("state") == "running":
                saved["state"] = "failed"
                saved["error"] = "Service restarted while syncing"

            _sync_states[school_id].update(saved)

    except Exception as error:
        print(f"[RAG Sync] could not read the saved state: {error}")


for _school_id in tenants.SCHOOLS:
    _load_state(_school_id)


def _check_key(key: str | None):
    if key != INTERNAL_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service key",
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _run_sync(school_id: str | None = None):
    """Background sync of one school: its files/URLs -> chunks ->
    embeddings -> its own Pinecone namespace. Other schools untouched."""
    school = tenants.get_school(school_id)
    state = _sync_states[school.id]

    async with _sync_lock:
        state.update(
            state="running",
            started_at=_now(),
            finished_at=None,
            result=None,
            error=None,
        )

        try:
            from backend.microservices.livekit_Rag_services.services.rag_engine.ingestion import (
                assemble_knowledge_base,
            )

            print(f"[RAG Sync] assembling the knowledge base of {school.name}...")
            started = time.monotonic()
            chunks = await assemble_knowledge_base(
                pdf_path=school.pdf_dir,
                text_path=school.text_dir,
                urls_path=school.urls_file,
            )
            print(f"[RAG Sync] assembled in {time.monotonic() - started:.1f}s")

            if not chunks:
                raise RuntimeError(
                    f"No content found for {school.name} — check {school.pdf_dir}, "
                    f"{school.text_dir} and {school.urls_file}"
                )

            print(f"[RAG Sync] {len(chunks)} chunks -> Pinecone")
            uploading = time.monotonic()
            result = await rebuild_vector_store(chunks, namespace=school.namespace)
            print(f"[RAG Sync] uploaded in {time.monotonic() - uploading:.1f}s")

            # How many chunks came from each file - the admin panel
            # displays this. Asking Pinecone for the counts is
            # expensive, and here they are already at hand.
            counts = {}
            for chunk in chunks:
                source = (chunk.metadata or {}).get("source")
                if source:
                    key = os.path.realpath(source) if os.path.exists(source) else source
                    counts[key] = counts.get(key, 0) + 1

            state["sources"] = counts
            _save_state(school.id)

            state.update(
                state="success",
                finished_at=_now(),
                result=result,
            )
            _save_state(school.id)
            print(f"[RAG Sync] done: {result}")

        except Exception as exc:
            state.update(
                state="failed",
                finished_at=_now(),
                error=f"{type(exc).__name__}: {exc}",
            )
            _save_state(school.id)
            print(f"[RAG Sync] fail: {exc}")


# ============================================================
# SYNC
# ============================================================

@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_knowledge_base(
    x_internal_key: str | None = Header(default=None),
    school: str | None = None,
):
    """
    Knowledge base dobara banayein.

    Runs in the background - so a 202 comes back immediately.
    Progress /rag/status se dekhein.
    """
    _check_key(x_internal_key)

    if _sync_lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A sync is already running.",
        )

    asyncio.create_task(_run_sync(school))

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
    school: str | None = None,
):
    """Pinecone index ki halat aur aakhri sync ka nateeja - one school."""
    _check_key(x_internal_key)
    chosen = tenants.get_school(school)

    try:
        stats = await get_index_stats(namespace=chosen.namespace)
    except Exception as exc:
        stats = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "school": chosen.id,
        "index": stats,
        "last_sync": sync_state(chosen.id),
    }
