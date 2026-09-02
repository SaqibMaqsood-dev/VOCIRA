from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.helper_functions.database.session import get_db

from backend.microservices.auth_services.schema import user_schema

from backend.microservices.livekit_Rag_services.models.session_model import (
    Session,
    SessionStatus,
)

from backend.microservices.livekit_Rag_services.models.escalation_model import (
    Escalation,
    EscalationStatus,
)

from backend.microservices.livekit_Rag_services.models.message_model import (
    Message,
)

from backend.microservices.livekit_Rag_services.schema.session_schema import (
    SessionResponse,
)

from backend.microservices.livekit_Rag_services.schema.escalation_schema import (
    EscalationResponse,
    EscalationPatch,
)

from backend.microservices.livekit_Rag_services.schema import (
    livekit_schema,
)

from backend.microservices.livekit_Rag_services.services.rbac.admin import (
    require_admin,
)

from backend.microservices.livekit_Rag_services.repository.session_repository import (
    SessionRepository,
)

from backend.microservices.livekit_Rag_services.services.router_services.escalation_service import (
    EscalationService,
)

from backend.microservices.livekit_Rag_services.services.router_services.livekit_services import (
    LivekitServices,
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


session_repository = SessionRepository()
escalation_service = EscalationService()
livekit_service    = LivekitServices()


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@router.get("/dashboard")
async def get_admin_dashboard(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    total_sessions = await db.scalar(
        select(func.count(Session.id))
    )

    active_sessions = await db.scalar(
        select(func.count(Session.id)).where(
            Session.status == SessionStatus.active
        )
    )

    closed_sessions = await db.scalar(
        select(func.count(Session.id)).where(
            Session.status == SessionStatus.closed
        )
    )

    total_messages = await db.scalar(
        select(func.count(Message.id))
    )

    total_escalations = await db.scalar(
        select(func.count(Escalation.id))
    )

    pending_escalations = await db.scalar(
        select(func.count(Escalation.id)).where(
            Escalation.status == EscalationStatus.pending
        )
    )

    resolved_escalations = await db.scalar(
        select(func.count(Escalation.id)).where(
            Escalation.status == EscalationStatus.resolved
        )
    )

    return {
        "total_sessions": total_sessions or 0,
        "active_sessions": active_sessions or 0,
        "closed_sessions": closed_sessions or 0,
        "total_messages": total_messages or 0,
        "total_escalations": total_escalations or 0,
        "pending_escalations": pending_escalations or 0,
        "resolved_escalations": resolved_escalations or 0,
    }


# =========================================================
# ALL SESSIONS
# =========================================================

@router.get(
    "/sessions",
    response_model=List[SessionResponse],
)
async def get_all_sessions(
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    return await session_repository.get_all_sessions(
        db=db,
        limit=limit,
        skip=skip,
    )


# =========================================================
# SINGLE SESSION
# =========================================================

@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    session = await session_repository.get_by_id(
        db=db,
        id=session_id,
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    return session


# =========================================================
# ALL ESCALATIONS
# =========================================================

@router.get(
    "/escalations",
    response_model=List[EscalationResponse],
)
async def get_all_escalations(
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    return await escalation_service.get_all_escalations(
        db=db,
        limit=limit,
        skip=skip,
    )


# =========================================================
# SINGLE ESCALATION
# =========================================================

@router.get(
    "/escalations/{escalation_id}",
    response_model=EscalationResponse,
)
async def get_escalation(
    escalation_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    return await escalation_service.get_escalation_by_id(
        db=db,
        id_value=escalation_id,
    )


# =========================================================
# UPDATE ESCALATION
# =========================================================

@router.patch(
    "/escalations/{escalation_id}",
    response_model=EscalationResponse,
)
async def update_escalation(
    escalation_id: UUID,
    request: EscalationPatch,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    return await escalation_service.partial_update_escalation(
        db=db,
        id_value=escalation_id,
        request=request,
    )



# =========================================================
# ADMIN ACCEPT CALL
# =========================================================

@router.post(
    "/calls/accept",
)
async def admin_accept_call(
    request: livekit_schema.AdminAcceptCallRequest,
    db: AsyncSession = Depends(get_db),
    admin: user_schema.User = Depends(require_admin),
):
    """
    Admin accepts a pending escalation.

    The admin receives a LiveKit token for the
    existing user's room.

    Session:
        handler = admin

    Escalation:
        remains pending until the call ends.
    """

    return await livekit_service.accept_admin_call(
        db=db,
        current_user=admin,
        escalation_id=request.escalation_id,
    )


# =========================================================
# ADMIN END CALL
# =========================================================

@router.post(
    "/calls/end",
)
async def admin_end_call(
    request: livekit_schema.AdminAcceptCallRequest,
    db: AsyncSession = Depends(get_db),
    admin: user_schema.User = Depends(require_admin),
):
    """
    Admin ends the active admin-handled call.

    This will:

    1. Delete the existing LiveKit room.
    2. Close the session.
    3. Set session.end_at.
    4. Resolve the escalation.
    """

    return await livekit_service.admin_end_call(
        db=db,
        current_user=admin,
        escalation_id=request.escalation_id,
    )
