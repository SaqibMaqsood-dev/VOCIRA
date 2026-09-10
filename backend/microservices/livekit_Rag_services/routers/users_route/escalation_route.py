from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.microservices.livekit_Rag_services.services.router_services.escalation_service import (
    EslcalationService,
)

from backend.microservices.livekit_Rag_services.schema.escalation_schema import (
    CreateEscalation,
    EscalationPatch
    
)

from backend.helper_functions.database.session import get_db

from backend.helper_functions.token_service.access_tokken.get_current_user import (
    current_user,
)

from backend.helper_functions.token_service.access_tokken.require_admin import (
    require_admin,
)




router = APIRouter(
    prefix="/escalations",
    tags=["Escalations"],
)

escalation_service = EslcalationService()


# ============================================================
# CREATE ESCALATION
# ============================================================

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
)
async def create_escalation(
    data: CreateEscalation,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(current_user)
):
    return await escalation_service.create_escalation(
        db=db,
        data=data,
    )


# ============================================================
# GET ALL ESCALATIONS
# ============================================================

@router.get(
    "/",
)
async def get_all_escalations(
    limit: int = 10,
    skip: int = 0,
    db: AsyncSession = Depends(get_db),
    # This carried only `current_user` before - meaning ANY
    # logged-in parent could see every escalation, other families'
    # questions included. This is the full list, so it has to be
    # admin-only.
    admin=Depends(require_admin),
):
    return await escalation_service.get_all_escalations(
        db=db,
        limit=limit,
        skip=skip,
    )


# ============================================================
# GET ESCALATION BY ID
# ============================================================

@router.get(
    "/{id_value}",
)
async def get_escalation_by_id(
    id_value: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(current_user)
):
    return await escalation_service.get_escalation_by_id(
        db=db,
        id_value=id_value,
    )


# ============================================================
# GET OCCURRED ESCALATIONS / STATS
# ============================================================

@router.get(
    "/stats/occurred",
)
async def get_occurred_escalations(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(current_user)
):
    return await escalation_service.get_occurred_escalations(
        db=db,
    )


# ============================================================
# FULL UPDATE
# ============================================================

@router.put(
    "/{id_value}",
)
async def update_escalation(
    id_value: int,
    request: CreateEscalation,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(current_user)
):
    return await escalation_service.update_escalation(
        db=db,
        id_value=id_value,
        request=request,
    )


# ============================================================
# PARTIAL UPDATE
# ============================================================

@router.patch(
    "/{id_value}",
)
async def partial_update_escalation(
    id_value: int,
    request: EscalationPatch,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(current_user)
):
    return await escalation_service.partial_update_escalation(
        db=db,
        id_value=id_value,
        request=request,
    )


# ============================================================
# DELETE ESCALATION
# ============================================================

@router.delete(
    "/{id_value}",
)
async def delete_escalation(
    id_value: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(current_user)
):
    return await escalation_service.delete_escalation(
        db=db,
        id_value=id_value,
    )


# ============================================================
# ASSIGN ESCALATION TO ADMIN
# ============================================================

@router.patch(
    "/{id_value}/assign/{admin_id}",
)
async def assign_escalation(
    id_value: int,
    admin_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(current_user)
):
    return await escalation_service.assign_escalation(
        db=db,
        id_value=id_value,
        admin_id=admin_id,
    )