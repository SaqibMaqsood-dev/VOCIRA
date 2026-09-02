from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.helper_functions.database.session import get_db

from backend.helper_functions.token_service.access_tokken.get_current_user import (
    current_user,
)

from backend.microservices.auth_services.schema import user_schema

from backend.microservices.livekit_Rag_services.schema import (
    livekit_schema,
)

from backend.microservices.livekit_Rag_services.services.router_services.livekit_services import (
    LivekitServices,
)


livekit_service = LivekitServices()


router = APIRouter(
    prefix="/livekit",
    tags=["Livekit"],
)


# ============================================================
# USER LIVEKIT TOKEN
# ============================================================

@router.post(
    "/live_kit/token",
    response_model=livekit_schema.LiveKitTokenResponse,
)
async def room_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: user_schema.User = Depends(current_user),
):
    return await livekit_service.create_user_room_token(
        db=db,
        current_user=current_user,
        request=request,
    )


# ============================================================
# GUEST LIVEKIT TOKEN
# ============================================================

@router.post(
    "/guest/live_kit/token",
)
async def guest_room_token():
    return await livekit_service.create_guest_room_token()


# ============================================================
# ADMIN ACCEPT CALL
# ============================================================

@router.post(
    "/admin/accept-call",
)
async def admin_accept_call(
    request: livekit_schema.AdminAcceptCallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: user_schema.User = Depends(current_user),
):
    """
    Admin accepts an active escalation and receives
    a LiveKit token for the existing caller room.

    Session:
        handler = admin

    Escalation:
        status = pending

    The escalation is resolved only when the admin
    ends the call.
    """

    return await livekit_service.accept_admin_call(
        db=db,
        current_user=current_user,
        escalation_id=request.escalation_id,
    )


# ============================================================
# ADMIN END CALL
# ============================================================

@router.post(
    "/admin/end-call",
)
async def admin_end_call(
    request: livekit_schema.AdminAcceptCallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: user_schema.User = Depends(current_user),
):
    """
    Admin ends an active admin-handled call.

    This will:

    1. Verify that the current user is an admin.
    2. Find the escalation.
    3. Find the related message.
    4. Find the related session.
    5. Verify that the session is handled by admin.
    6. Delete the existing LiveKit room.
    7. Close the session.
    8. Set session.end_at.
    9. Resolve the escalation.
    """

    return await livekit_service.admin_end_call(
        db=db,
        current_user=current_user,
        escalation_id=request.escalation_id,
    )
