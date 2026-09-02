from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.helper_functions.database.session import get_db

from backend.microservices.livekit_Rag_services.schema.escalation_schema import (
    CreateEscalation,
    EscalationPatch,
)

from backend.microservices.livekit_Rag_services.services.router_services.escalation_service import (
    EscalationService,
)


router = APIRouter(
    prefix="/escalations",
    tags=["Escalations"],
)


escalation_service = EscalationService()


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
):
    return await escalation_service.create_escalation(
        db=db,
        data=data,
    )


# ============================================================
# GET OCCURRED ESCALATIONS / STATS
# ============================================================

@router.get(
    "/stats/occurred",
)
async def get_occurred_escalations(
    db: AsyncSession = Depends(get_db),
):
    return await escalation_service.get_occurred_escalations(
        db=db,
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
    id_value: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await escalation_service.get_escalation_by_id(
        db=db,
        id_value=id_value,
    )


# ============================================================
# PARTIAL UPDATE
# ============================================================

@router.patch(
    "/{id_value}",
)
async def partial_update_escalation(
    id_value: UUID,
    request: EscalationPatch,
    db: AsyncSession = Depends(get_db),
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
    id_value: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await escalation_service.delete_escalation(
        db=db,
        id_value=id_value,
    )
