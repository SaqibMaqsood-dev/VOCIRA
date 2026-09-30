"""
Endpoints for the admin panel.

The admin side of the frontend used to run entirely on the fake data
in `data.js` - 122 hardcoded lines and no backend call at all. The
backend already had escalations, messages and sessions; what it
lacked was an admin-wide view of them (that is, across ALL users):
`/sessions/stats` only counts the caller's own.

Every endpoint sits behind `require_admin`.
"""

import json

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.helper_functions.database.session import get_db
from backend.helper_functions.token_service.access_tokken.require_admin import (
    require_admin,
)
from backend.microservices.livekit_Rag_services.models.escalation_model import (
    Escalation,
    EscalationStatus,
)
from backend.microservices.livekit_Rag_services.models.message_model import (
    Message,
    SenderTypeEnum,
)
from backend.microservices.livekit_Rag_services.models.session_model import Session
from backend.microservices.auth_services.models.user_model import Users


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)


# The question is the message the user spoke; the answer is the
# one the agent gave back.
_USER_SIDE = (SenderTypeEnum.user, SenderTypeEnum.guest)


def _status_for(message_id, escalated_ids: set) -> str:
    """The frontend thinks in three states."""
    return "Escalated" if message_id in escalated_ids else "Resolved"


# =========================================================
# DASHBOARD
# =========================================================

@router.get("/stats")
async def admin_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """The cards across the top of the dashboard, plus both charts."""

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)

    async def count_messages(since=None):
        stmt = select(func.count()).select_from(Message).where(
            Message.sender_type.in_(_USER_SIDE)
        )
        if since is not None:
            stmt = stmt.where(Message.created_at >= since)
        return (await db.execute(stmt)).scalar_one()

    today = await count_messages(today_start)
    week = await count_messages(week_start)
    total = await count_messages()

    escalated = (
        await db.execute(select(func.count()).select_from(Escalation))
    ).scalar_one()

    sessions = (
        await db.execute(select(func.count()).select_from(Session))
    ).scalar_one()

    # ---- pichhle 7 din, roz ke sawal ----
    per_day_rows = (
        await db.execute(
            select(
                func.date(Message.created_at).label("day"),
                func.count().label("value"),
            )
            .where(
                Message.sender_type.in_(_USER_SIDE),
                Message.created_at >= week_start,
            )
            .group_by("day")
            .order_by("day")
        )
    ).all()

    counts = {str(row.day): row.value for row in per_day_rows}

    queries_per_day = []
    for offset in range(6, -1, -1):
        day = (today_start - timedelta(days=offset)).date()
        queries_per_day.append(
            {
                "day": day.strftime("%a"),
                "date": str(day),
                "value": counts.get(str(day), 0),
            }
        )

    # ---- kitne AI ne hal kiye, kitne aage bheje gaye ----
    resolved = max(total - escalated, 0)
    denominator = total or 1

    escalation_rate = [
        {
            "label": "AI Resolved",
            "value": round(100 * resolved / denominator),
        },
        {
            "label": "Escalated",
            "value": round(100 * escalated / denominator),
        },
    ]

    return {
        "today": today,
        "week": week,
        "total": total,
        "escalated": escalated,
        "sessions": sessions,
        "queriesPerDay": queries_per_day,
        "escalationRate": escalation_rate,
    }


# =========================================================
# SAARE SAWAL (sab users ke)
# =========================================================

@router.get("/queries")
async def admin_queries(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """
    A question paired with its answer.

    Messages all live in one table, so the ai-message that follows a
    user-message in the same session is taken to be its answer - the
    same order the voice pipeline writes them in.
    """

    rows = (
        await db.execute(
            select(Message)
            .order_by(Message.created_at.desc())
            .limit(limit * 2 + 20)
            .offset(skip)
        )
    ).scalars().all()

    escalated_ids = set(
        (
            await db.execute(select(Escalation.message_id))
        ).scalars().all()
    )

    # oldest first, so an answer is easy to find
    rows = list(reversed(rows))

    # -----------------------------------------------------------
    # WHO ASKED
    #
    # Every row just said "Parent" - the admin panel could not tell
    # one guardian's questions from another's, which is exactly what
    # grouping by guardian needs. Message.user_id already points at
    # the same `users` table auth_services owns (Users.extend_existing
    # keeps both services pointed at one physical table), so this is
    # a single batched lookup, not a query per row.
    # -----------------------------------------------------------

    user_ids = {
        row.user_id
        for row in rows
        if row.sender_type is SenderTypeEnum.user and row.user_id
    }

    users_by_id = {}
    if user_ids:
        user_rows = (
            await db.execute(
                select(Users.user_id, Users.name, Users.email)
                .where(Users.user_id.in_(user_ids))
            )
        ).all()
        users_by_id = {
            uid: {"name": name, "email": email}
            for uid, name, email in user_rows
        }

    out = []

    for index, row in enumerate(rows):

        if row.sender_type not in _USER_SIDE:
            continue

        answer = None

        for later in rows[index + 1:]:
            if later.session_id != row.session_id:
                continue
            if later.sender_type is SenderTypeEnum.ai:
                answer = later.content
            break

        if row.sender_type is SenderTypeEnum.guest or not row.user_id:
            user_key = "guest"
            user_name = "Guest"
            user_email = None
        else:
            info = users_by_id.get(row.user_id)
            user_key = str(row.user_id)
            user_name = (info or {}).get("name") or "Parent"
            user_email = (info or {}).get("email")

        out.append(
            {
                "id": str(row.id),
                "sessionId": str(row.session_id),
                "userId": user_key,
                "user": user_name,
                "userEmail": user_email,
                "question": row.content,
                "response": answer or "—",
                "status": _status_for(row.id, escalated_ids),
                "intent": row.intent,
                "timestamp": row.created_at.isoformat(),
            }
        )

    out.reverse()          # naye pehle
    return out[:limit]


# =========================================================
# ESCALATIONS
# =========================================================

@router.get("/escalations")
async def admin_escalations(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """An escalation together with the question that caused it."""

    rows = (
        await db.execute(
            select(Escalation, Message)
            .join(Message, Message.id == Escalation.message_id)
            .order_by(Escalation.created_at.desc())
            .limit(limit)
            .offset(skip)
        )
    ).all()

    return [
        {
            "id": str(escalation.id),
            "question": message.content,
            "sessionId": str(message.session_id),
            "status": escalation.status.value
            if hasattr(escalation.status, "value")
            else str(escalation.status),
            "userId": str(escalation.user_id) if escalation.user_id else None,
            "time": escalation.created_at.isoformat(),
        }
        for escalation, message in rows
    ]


# =========================================================
# KNOWLEDGE BASE
# =========================================================

async def _school_kinds(school: str | None):
    """The chosen school, and its document folders."""
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.rag_engine import documents

    await tenants.refresh(force=not tenants.is_known(school))
    chosen = tenants.get_school(school)
    return chosen, documents.kinds_for(chosen.pdf_dir, chosen.text_dir)


class SchoolRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    name_ur: str | None = Field(default=None, max_length=80)
    helpline: str = Field(min_length=7, max_length=30)
    records: str | None = None
    records_env_prefix: str | None = Field(default=None, max_length=40)


@router.post("/schools", status_code=201)
async def admin_add_school(request: SchoolRequest):
    """
    Add a school - no code change. It gets its own knowledge base
    (namespace and folders, from its id) straight away; documents are
    added on the Knowledge page, and guests reach it by its link.
    """
    from backend.microservices.livekit_Rag_services.services import tenants

    try:
        school = await tenants.create_school(**request.model_dump())
    except tenants.TenantError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))

    print(f"[Schools] added: {school.id} ({school.name})")
    return {"id": school.id, "name": school.name, "namespace": school.namespace,
            "guest_link": f"/assistant?school={school.id}"}


@router.patch("/schools/{school_id}")
async def admin_update_school(school_id: str, request: SchoolRequest):
    """Change a school added from the panel (name, helpline, records)."""
    from backend.microservices.livekit_Rag_services.services import tenants

    try:
        school = await tenants.update_school(school_id, **request.model_dump())
    except tenants.TenantError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")

    return {"id": school.id, "name": school.name}


@router.delete("/schools/{school_id}")
async def admin_delete_school(school_id: str):
    """
    Remove a school added from the panel. Its knowledge is cleared from
    the index so it can never answer again; its files stay on disk.
    """
    import asyncio

    from backend.microservices.livekit_Rag_services.routers.users_route import rag_route
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import clear_namespace

    if rag_route._sync_lock.locked():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A sync is running - try again shortly.")

    try:
        school = await tenants.delete_school(school_id)
    except tenants.TenantError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")

    try:
        await clear_namespace(school.namespace)
    except Exception as exc:
        print(f"[Schools] could not clear {school.namespace}: {exc}")

    # Its sync record goes too; its uploaded files stay on disk.
    import os

    rag_route._sync_states.pop(school.id, None)
    try:
        os.remove(rag_route._state_file(school.id))
    except FileNotFoundError:
        pass

    print(f"[Schools] removed: {school.id}")
    return {"removed": school.id}


@router.get("/schools")
async def admin_schools():
    """
    The schools this deployment serves - one agent, a knowledge base and
    a records connector per school. Feeds the knowledge page's picker
    and the Schools page.
    """
    from backend.microservices.livekit_Rag_services.routers.users_route import (
        rag_route,
    )
    from backend.microservices.livekit_Rag_services.services import tenants
    from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
        namespace_vector_counts,
    )

    await tenants.refresh(force=True)

    try:
        counts = await namespace_vector_counts()
    except Exception as exc:
        print(f"[Schools] could not read the vector counts: {exc}")
        counts = None

    schools = []
    for school in tenants.public_list():
        last = rag_route.sync_state(school["id"])
        schools.append({
            **school,
            "vectors": None if counts is None else counts.get(school["namespace"], 0),
            "last_sync": {"state": last.get("state"), "finished_at": last.get("finished_at")},
            "guest_link": f"/assistant?school={school['id']}",
        })

    return {"schools": schools, "default": tenants.DEFAULT_SCHOOL_ID}


@router.get("/knowledge")
async def admin_knowledge(school: str | None = None):
    """
    Knowledge base ki asli halat.

    This page used to show a fake list of "articles". The real
    knowledge base is the Pinecone index - that is where RAG answers
    come from. /rag/status returns the same thing, but it sits behind
    an internal key, hence this admin-facing copy.
    """

    from backend.microservices.livekit_Rag_services.routers.users_route import (
        rag_route,
    )
    from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
        get_index_stats,
    )

    chosen, _ = await _school_kinds(school)

    try:
        stats = await get_index_stats(namespace=chosen.namespace)
    except Exception as exc:
        stats = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "school": chosen.id,
        "index": stats,
        "last_sync": rag_route.sync_state(chosen.id),
    }


@router.post("/knowledge/sync", status_code=202)
async def admin_sync_knowledge(school: str | None = None):
    """One school's knowledge base dobara banayein (background mein)."""

    import asyncio

    from backend.microservices.livekit_Rag_services.routers.users_route import (
        rag_route,
    )

    # One sync at a time across schools - they share the index.
    if rag_route._sync_lock.locked():
        return {"state": "running", "message": "A sync is already running."}

    chosen, _ = await _school_kinds(school)
    asyncio.create_task(rag_route._run_sync(chosen.id))

    return {
        "state": "started",
        "message": "Sync started in the background.",
    }


@router.patch("/escalations/{escalation_id}/status")
async def set_escalation_status(
    escalation_id: str,
    new_status: EscalationStatus,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Escalation ka status badlein (Resolve / Open waghera)."""

    escalation = (
        await db.execute(
            select(Escalation).where(Escalation.id == escalation_id)
        )
    ).scalar_one_or_none()

    if escalation is None:
        return {"updated": False, "reason": "not found"}

    escalation.status = new_status
    await db.commit()

    return {"updated": True, "id": escalation_id, "status": new_status.value}


# =========================================================
# KNOWLEDGE BASE - DOCUMENTS
#
# There used to be exactly one way to add new data: put the file on
# the server by hand, then press sync. It can now be done from the
# panel itself.
# =========================================================

@router.get("/knowledge/documents")
async def admin_knowledge_documents(school: str | None = None):
    """
    Which documents exist, and how many chunks each produced.

    The chunk counts come from the last sync. A file added after that
    has a null count - meaning "not in the index yet, run a sync".
    """

    from backend.microservices.livekit_Rag_services.routers.users_route import (
        rag_route,
    )
    from backend.microservices.livekit_Rag_services.services.rag_engine import (
        documents,
    )

    chosen, kinds = await _school_kinds(school)
    sources = rag_route.sync_state(chosen.id).get("sources") or {}

    docs = documents.list_documents(chunks_by_source=sources, kinds=kinds)

    return {
        "documents": docs,
        "total": len(docs),
        "indexed": sum(1 for d in docs if d["indexed"]),
        "chunks": sum(d["chunks"] or 0 for d in docs),
    }


@router.post("/knowledge/documents", status_code=201)
async def admin_upload_document(file: UploadFile = File(...), school: str | None = None):
    """PDF ya TXT upload karein."""

    from backend.microservices.livekit_Rag_services.services.rag_engine import (
        documents,
    )

    content = await file.read()

    try:
        _, kinds = await _school_kinds(school)
        saved = documents.save_upload(
            filename=file.filename,
            content=content,
            kinds=kinds,
        )
    except documents.DocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )

    print(f"[Knowledge] upload: {saved['name']} ({saved['size']} bytes)")

    return {**saved, "message": "Uploaded. Run a sync to index it."}


class NoteRequest(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    text: str = Field(min_length=10, max_length=20000)


@router.post("/knowledge/notes", status_code=201)
async def admin_add_note(request: NoteRequest, school: str | None = None):
    """
    Write a short note directly - no need to produce a PDF.

    The note lands in the same text_files folder as a .txt, so as far
    as ingestion is concerned it is no different from any other file.
    """

    from backend.microservices.livekit_Rag_services.services.rag_engine import (
        documents,
    )

    try:
        _, kinds = await _school_kinds(school)
        saved = documents.save_note(
            title=request.title,
            text=request.text,
            kinds=kinds,
        )
    except documents.DocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )

    print(f"[Knowledge] note: {saved['name']}")

    return {**saved, "message": "Saved. Run a sync to index it."}


@router.delete("/knowledge/documents/{name}")
async def admin_delete_document(name: str, school: str | None = None):
    """Document hatayein. Index se wo agli sync par nikalta hai."""

    from backend.microservices.livekit_Rag_services.services.rag_engine import (
        documents,
    )

    try:
        _, kinds = await _school_kinds(school)
        removed = documents.delete_document(name, kinds=kinds)
    except documents.DocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    print(f"[Knowledge] deleted: {name}")

    return {"deleted": True, "name": name}


# =========================================================
# ERPNEXT GUARDIANS
#
# The admin panel's Users page used to ask for a Guardian ID when
# creating an account - typed in by hand. One character out of place
# and the account reached no child at all, and the mistake only
# surfaced when the parent complained.
#
# It is now picked from a list, and the email is filled in from
# ERPNext automatically. This endpoint lives here (rather than in the
# auth service) because this service is the one with ERP access.
# =========================================================

@router.get("/guardians")
async def admin_guardians():
    """
    ERPNext ke saare guardians - naam, email aur kitne bachche.

    email_address can be empty. We do not invent one in that case:
    the account is created against the email the parent will log in
    with, and a guessed address is of no use to them. The panel tells
    the school to fill the email into ERPNext first.
    """

    from backend.microservices.livekit_Rag_services.services.erp_services.ERP_client import (
        ERPClient,
    )

    client = ERPClient()

    try:
        rows = await client.get(
            "/api/resource/Guardian",
            params={
                "limit_page_length": 0,
                "fields": json.dumps(
                    ["name", "guardian_name", "email_address", "mobile_number"]
                ),
                "order_by": "guardian_name asc",
            },
        )
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach the school system: {error}",
        )

    guardians = (rows or {}).get("data") or []

    # How many children each guardian has - in a single call, not
    # one call per guardian
    try:
        links = (
            await client.get(
                "/api/resource/Student Guardian",
                params={
                    "limit_page_length": 0,
                    "parent": "Student",
                    "fields": json.dumps(["guardian"]),
                },
            )
        ).get("data") or []
    except Exception:
        links = []

    counts = {}
    for link in links:
        key = link.get("guardian")
        if key:
            counts[key] = counts.get(key, 0) + 1

    return [
        {
            "id": g["name"],
            "name": g.get("guardian_name") or g["name"],
            "email": (g.get("email_address") or "").strip() or None,
            "mobile": g.get("mobile_number"),
            "students": counts.get(g["name"], 0),
        }
        for g in guardians
    ]
