"""
Admin panel ke liye endpoints.

Frontend ka admin hissa pehle poora `data.js` ke jhoote data par
chalta tha - 122 lines hardcoded, koi backend call nahi. Backend
mein escalations/messages/sessions sab pehle se mojood thay, bas
admin ke nazariye se (yaani SAARE users ka) koi endpoint nahi tha:
`/sessions/stats` sirf apne user ki ginti deta hai.

Har endpoint `require_admin` ke peeche hai.
"""

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


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)


# Sawal wo message hai jo user ne kaha; jawab wo jo agent ne diya.
_USER_SIDE = (SenderTypeEnum.user, SenderTypeEnum.guest)


def _status_for(message_id, escalated_ids: set) -> str:
    """Frontend teen haalaton mein sochta hai."""
    return "Escalated" if message_id in escalated_ids else "Resolved"


# =========================================================
# DASHBOARD
# =========================================================

@router.get("/stats")
async def admin_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Dashboard ke upar wale cards + dono chart."""

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
    Sawal aur us ka jawab, ek jodi ban kar.

    Messages ek hi table mein hain, is liye har user-message ke
    baad us ke session ka agla ai-message us ka jawab mana jata
    hai - wahi tarteeb jo voice pipeline likhti hai.
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

    # purane se naye - taake jawab dhoondna aasan ho
    rows = list(reversed(rows))

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

        out.append(
            {
                "id": str(row.id),
                "sessionId": str(row.session_id),
                "user": (
                    "Guest"
                    if row.sender_type is SenderTypeEnum.guest
                    else "Parent"
                ),
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
    """Escalation ke sath wo sawal bhi jis par wo bani thi."""

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

@router.get("/knowledge")
async def admin_knowledge():
    """
    Knowledge base ki asli halat.

    Frontend par ye page "articles" ki jhooti list dikhata tha. Asli
    knowledge base Pinecone ka index hai - RAG ke jawab wahin se
    bante hain. /rag/status bhi yehi deta hai magar wo internal key
    ke peeche hai, is liye admin ke liye yahan se.
    """

    from backend.microservices.livekit_Rag_services.routers.users_route import (
        rag_route,
    )
    from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
        get_index_stats,
    )

    try:
        stats = await get_index_stats()
    except Exception as exc:
        stats = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "index": stats,
        "last_sync": getattr(rag_route, "_last_sync", {"state": "unknown"}),
    }


@router.post("/knowledge/sync", status_code=202)
async def admin_sync_knowledge():
    """Knowledge base dobara banayein (background mein)."""

    import asyncio

    from backend.microservices.livekit_Rag_services.routers.users_route import (
        rag_route,
    )

    if rag_route._last_sync.get("state") == "running":
        return {"state": "running", "message": "A sync is already running."}

    asyncio.create_task(rag_route._run_sync())

    return {
        "state": "started",
        "message": "Sync started. Refresh in a moment.",
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
# Pehle naya data daalne ka sirf ek tareeqa tha: file server par
# manually rakho, phir sync dabao. Ab panel se hi ho jata hai.
# =========================================================

@router.get("/knowledge/documents")
async def admin_knowledge_documents():
    """
    Kaunse documents mojood hain, aur har ek se kitne chunks bane.

    Chunk ki ginti aakhri sync se aati hai. Jo file us ke baad rakhi
    gayi ho us ka count null hota hai - yaani "abhi index mein nahi,
    sync chalayein".
    """

    from backend.microservices.livekit_Rag_services.routers.users_route import (
        rag_route,
    )
    from backend.microservices.livekit_Rag_services.services.rag_engine import (
        documents,
    )

    sources = getattr(rag_route, "_last_sync", {}).get("sources") or {}

    docs = documents.list_documents(chunks_by_source=sources)

    return {
        "documents": docs,
        "total": len(docs),
        "indexed": sum(1 for d in docs if d["indexed"]),
        "chunks": sum(d["chunks"] or 0 for d in docs),
    }


@router.post("/knowledge/documents", status_code=201)
async def admin_upload_document(file: UploadFile = File(...)):
    """PDF ya TXT upload karein."""

    from backend.microservices.livekit_Rag_services.services.rag_engine import (
        documents,
    )

    content = await file.read()

    try:
        saved = documents.save_upload(
            filename=file.filename,
            content=content,
        )
    except documents.DocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )

    print(f"📄 [Knowledge] upload: {saved['name']} ({saved['size']} bytes)")

    return {**saved, "message": "Uploaded. Run a sync to index it."}


class NoteRequest(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    text: str = Field(min_length=10, max_length=20000)


@router.post("/knowledge/notes", status_code=201)
async def admin_add_note(request: NoteRequest):
    """
    Chhoti baat seedha likh dein - PDF banane ki zaroorat nahi.

    Note wahi text_files folder mein .txt ban kar jata hai, is liye
    ingestion ke liye us mein aur kisi file mein koi farq nahi.
    """

    from backend.microservices.livekit_Rag_services.services.rag_engine import (
        documents,
    )

    try:
        saved = documents.save_note(
            title=request.title,
            text=request.text,
        )
    except documents.DocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )

    print(f"📝 [Knowledge] note: {saved['name']}")

    return {**saved, "message": "Saved. Run a sync to index it."}


@router.delete("/knowledge/documents/{name}")
async def admin_delete_document(name: str):
    """Document hatayein. Index se wo agli sync par nikalta hai."""

    from backend.microservices.livekit_Rag_services.services.rag_engine import (
        documents,
    )

    try:
        removed = documents.delete_document(name)
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

    print(f"🗑️ [Knowledge] hataya: {name}")

    return {"deleted": True, "name": name}
