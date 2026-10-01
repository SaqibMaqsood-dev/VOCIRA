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
# WHICH SCHOOL A CALL GOES TO
# ============================================================

@router.get("/tenant/{address}")
async def school_at_address(address: str):
    """
    The school at an address - the subdomain the page was opened on
    (medicaps.vocira.com -> "medicaps"), or a school id from an older
    /s/<id> link. Only that one school, by name: there is no list of
    schools to ask for, so no school learns which others use Vocira.
    """
    from fastapi import HTTPException

    from backend.microservices.livekit_Rag_services.services import tenants

    await tenants.refresh()
    school = tenants.find_by_address(address)
    if school is None:
        # added a moment ago, perhaps
        await tenants.refresh(force=True)
        school = tenants.find_by_address(address)
    if school is None:
        raise HTTPException(status_code=404, detail="There is no school at this address.")
    return {"id": school.id, "name": school.name, "name_ur": school.name_ur,
            "subdomain": tenants.address_of(school)}


@router.get("/live_kit/school")
async def my_call_school(
    db: AsyncSession = Depends(get_db),
    current_user: user_schema.User = Depends(current_user),
):
    """
    The school a signed-in user's call goes to - their account's, read
    exactly as the call token reads it, so what the page shows is what
    the call does. A link or a choice on the page never changes it.
    """
    from sqlalchemy import select

    from backend.microservices.auth_services.models.user_model import Users
    from backend.microservices.livekit_Rag_services.services import tenants

    school_id = await db.scalar(select(Users.school_id).where(Users.user_id == current_user.user_id))
    await tenants.refresh(force=bool(school_id) and not tenants.is_known(school_id))
    school = tenants.get_school(school_id)
    return {"id": school.id, "name": school.name, "name_ur": school.name_ur, "from": "account"}


# ============================================================
# GUEST LIVEKIT TOKEN
# ============================================================

@router.post(
    "/guest/live_kit/token",
)
async def guest_room_token(language: str | None = None, school: str | None = None):
    return await livekit_service.create_guest_room_token(
        language=language,
        school=school,
    )


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
    """

    return await livekit_service.accept_admin_call(
        db=db,
        current_user=current_user,
        escalation_id=request.escalation_id,
    )