from typing import List

from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from database import database
from schema import escalation_schema
from services.escalation_services import escalation_logic

router = APIRouter(prefix="/escalations", tags=["Escalations"])


@router.post("/create_escalations", response_model=escalation_schema.EscalationResponse)
async def create_escalation(
    request: escalation_schema.CreateEscalation,
    db: AsyncSession = Depends(database.get_db)
):
    return await escalation_logic.create_escalation(db=db, request=request)


@router.get("/get_escalation", response_model=List[escalation_schema.EscalationResponse])
async def get_escalations(db: AsyncSession = Depends(database.get_db)):
    return await escalation_logic.get_all_escalations(db=db)


@router.get("/get_escalation/{id}", response_model=escalation_schema.EscalationResponse)
async def get_escalation_by_id(id: int, db: AsyncSession = Depends(database.get_db)):
    return await escalation_logic.get_escalation_by_id(db=db, id_value=id)


@router.delete("/delete_escalation/{id}")
async def delete_escalation(id: int, db: AsyncSession = Depends(database.get_db)):
    return await escalation_logic.delete_escalation(db=db, id_value=id)


@router.put("/update_escalation/{id}")
async def update_escalation(
    request: escalation_schema.CreateEscalation,
    id: int,
    db: AsyncSession = Depends(database.get_db)
):
    return await escalation_logic.update_escalation(db=db, id_value=id, request=request)


@router.patch("/update_partial_escalation/{id}")
async def partial_update_escalation(
    request: escalation_schema.EscalationPatch,
    id: int,
    db: AsyncSession = Depends(database.get_db)
):
    return await escalation_logic.partial_update_escalation(db=db, id_value=id, request=request)


@router.patch("/assign/{id}")
async def assign_escalation(
    id: int,
    admin_id: int,
    db: AsyncSession = Depends(database.get_db)
):
    return await escalation_logic.assign_escalation(db=db, id_value=id, admin_id=admin_id)