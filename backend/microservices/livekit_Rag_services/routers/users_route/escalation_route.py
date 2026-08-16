from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.helper_functions.database import get_db
from backend.microservices.livekit_Rag_services.schema import escalation_schema
from backend.microservices.livekit_Rag_services.services.router_services.escalation_service import EslcalationService

escalation_service = EslcalationService()



router = APIRouter(prefix="/escalations", tags=["Escalations"])


@router.post(
    "/create_escalations",
    response_model=escalation_schema.EscalationResponse
)
async def create_escalation(
    request: escalation_schema.CreateEscalation,
    db: AsyncSession = Depends(get_db)
):
    return await escalation_service.create_escalation(
        db=db,
        data=request
    )



@router.get(
    "/get_escalation",
    response_model=List[escalation_schema.EscalationResponse]
)
async def get_escalations(
    limit : int = 10, 
    skip  : int = 0,
    db: AsyncSession = Depends(get_db)
):
    return await escalation_service.get_all_escalations(db=db , limit = limit , skip = skip)


@router.get(
    "/get_escalation/{id}",
    response_model=escalation_schema.EscalationResponse
)
async def get_escalation_by_id(
    id: int,
    db: AsyncSession = Depends(get_db)
):
    return await escalation_service.get_escalation_by_id(
        db=db,
        id_value=id
    )


@router.delete("/delete_escalation/{id}")
async def delete_escalation(
    id: int,
    db: AsyncSession = Depends(get_db)
):
    return await escalation_service.delete_escalation(
        db=db,
        id_value=id
    )


@router.put("/update_escalation/{id}")
async def update_escalation(
    request: escalation_schema.CreateEscalation,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    return await escalation_service.update_escalation(
        db=db,
        id_value=id,
        request=request
    )


@router.patch("/update_partial_escalation/{id}")
async def partial_update_escalation(
    request: escalation_schema.EscalationPatch,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    return await escalation_service.partial_update_escalation(
        db=db,
        id_value=id,
        request=request
    )


@router.patch("/assign/{id}")
async def assign_escalation(
    id: int,
    admin_id: int,
    db: AsyncSession = Depends(get_db)
):
    return await escalation_service.assign_escalation(
        db=db,
        id_value=id,
        admin_id=admin_id
    )