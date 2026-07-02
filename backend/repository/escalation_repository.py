from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from models import escalation_model
from repository import base_repository


async def get_all_escalations(db: AsyncSession) -> Sequence[escalation_model.Escalation]:
    return await base_repository.get_all(db=db, model=escalation_model.Escalation)


async def get_escalation_by_id(db: AsyncSession, id_value: int) -> Optional[escalation_model.Escalation]:
    return await base_repository.get_by_id(db=db, model=escalation_model.Escalation, id_value=id_value)


async def create_escalation(db: AsyncSession, escalation: escalation_model.Escalation) -> escalation_model.Escalation:
    return await base_repository.create(db=db, instance=escalation)


async def update_escalation(db: AsyncSession, escalation: escalation_model.Escalation, data: dict) -> escalation_model.Escalation:
    return await base_repository.update(db=db, instance=escalation, data=data)


async def delete_escalation(db: AsyncSession, escalation: escalation_model.Escalation) -> None:
    await base_repository.delete_by_id(db=db, model=escalation_model.Escalation, id_value=escalation.id)


async def assign_escalation(db: AsyncSession, escalation: escalation_model.Escalation, admin_id: int) -> escalation_model.Escalation:
    return await base_repository.update(db=db, instance=escalation, data={"assigned_admin": admin_id})
