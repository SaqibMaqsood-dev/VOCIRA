from fastapi import HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from models import escalation_model
from repository import escalation_repository


async def create_escalation(db: AsyncSession, request):
    new_escalation = escalation_model.Escalation(
        user_id=1,
        status=request.status,
        message_id=5,
        assigned_admin=1,
    )
    return await escalation_repository.create_escalation(db=db, escalation=new_escalation)


async def get_all_escalations(db: AsyncSession):
    escalations = await escalation_repository.get_all_escalations(db=db)
    if not escalations:
        raise HTTPException(404, "No escalations found")
    return escalations


async def get_escalation_by_id(db: AsyncSession, id_value: int):
    escalation = await escalation_repository.get_escalation_by_id(db=db, id_value=id_value)
    if not escalation:
        raise HTTPException(404, f"No escalation found with id {id_value}")
    return escalation


async def update_escalation(db: AsyncSession, id_value: int, request):
    escalation = await escalation_repository.get_escalation_by_id(db=db, id_value=id_value)
    if not escalation:
        raise HTTPException(404, f"No escalation found with id {id_value}")

    data = {"user_id": request.user_id, "message_id": request.message_id}
    await escalation_repository.update_escalation(db=db, escalation=escalation, data=data)
    return {"message": "Escalation updated successfully"}


async def partial_update_escalation(db: AsyncSession, id_value: int, request):
    escalation = await escalation_repository.get_escalation_by_id(db=db, id_value=id_value)
    if not escalation:
        raise HTTPException(404, f"No escalation found with id {id_value}")

    data = request.model_dump(exclude_unset=True)
    await escalation_repository.update_escalation(db=db, escalation=escalation, data=data)
    return {"message": "Escalation partially updated", "updated_fields": data}


async def delete_escalation(db: AsyncSession, id_value: int):
    escalation = await escalation_repository.get_escalation_by_id(db=db, id_value=id_value)
    if not escalation:
        raise HTTPException(404, f"No escalation found with id {id_value}")

    await escalation_repository.delete_escalation(db=db, escalation=escalation)
    return {"message": f"Escalation deleted with id {id_value}"}


async def assign_escalation(db: AsyncSession, id_value: int, admin_id: int):
    escalation = await escalation_repository.get_escalation_by_id(db=db, id_value=id_value)
    if not escalation:
        raise HTTPException(404, "Escalation not found")

    await escalation_repository.assign_escalation(db=db, escalation=escalation, admin_id=admin_id)
    return {"message": f"Escalation assigned to admin {admin_id}"}