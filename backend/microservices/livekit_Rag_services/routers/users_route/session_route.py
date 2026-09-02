from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.helper_functions.database.session import get_db

from backend.microservices.livekit_Rag_services.schema import (
    session_schema,
)

from backend.microservices.livekit_Rag_services.services.router_services.session_service import (
    SessionService,
)

from backend.helper_functions.token_service.access_tokken.get_current_user import (
    current_user,
)


# =========================================================
# ROUTER
# =========================================================

router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"],
)

ss_service = SessionService()


# =========================================================
# CREATE MY SESSION
# =========================================================

@router.post(
    "/",
    response_model=session_schema.SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_session(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(current_user),
):
    """
    Create a session for the authenticated user.

    The session is committed to PostgreSQL before
    its ID is published to RabbitMQ.
    """

    return await ss_service.create_session(
        db=db,
        user_id=current_user.user_id,
    )


# =========================================================
# GET MY SESSIONS
# =========================================================

@router.get(
    "/",
    response_model=List[session_schema.SessionResponse],
)
async def get_my_sessions(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(current_user),
    limit: int = 10,
    skip: int = 0,
):
    print("=" * 70)
    print("🔐 CURRENT USER:", current_user)
    print("🆔 CURRENT USER ID:", current_user.user_id)
    print("=" * 70)

    sessions = await ss_service.get_user_sessions(
        db=db,
        user_id=current_user.user_id,
        limit=limit,
        skip=skip,
    )

    print(
        f"📦 [Sessions] Returned: {len(sessions)}"
    )

    return sessions


# =========================================================
# DASHBOARD STATS
# =========================================================

@router.get(
    "/stats",
)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(current_user),
):
    return await ss_service.get_dashboard_stats(
        db=db,
        user_id=current_user.user_id,
    )


# =========================================================
# GET MY SESSION BY ID
# =========================================================

@router.get(
    "/{id}",
    response_model=session_schema.SessionResponse,
)
async def get_session_with_id(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(current_user),
):
    return await ss_service.get_session_by_id(
        db=db,
        user_id=current_user.user_id,
        id_value=id,
    )


# =========================================================
# CLOSE MY SESSION
# =========================================================

@router.patch(
    "/{id}/close",
    response_model=session_schema.SessionResponse,
)
async def close_my_session(
    id: UUID,
    current_user=Depends(current_user),
):
    """
    Close the authenticated user's session.

    The SessionService creates its own database transaction.

    When closed:

        status  -> closed
        end_at  -> current timestamp

    The existing handler is preserved:

        ai
        OR
        admin

    Duration is calculated from:

        end_at - start_at
    """

    return await ss_service.close_session_by_id(
        user_id=current_user.user_id,
        session_id=id,
    )