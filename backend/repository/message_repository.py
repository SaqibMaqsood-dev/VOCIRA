from typing import Optional, Sequence

from sqlalchemy import select, delete as sqlalchemy_delete
from sqlalchemy.ext.asyncio import AsyncSession

from models import message_model
from repository import base_repository


async def get_all_messages(db: AsyncSession) -> Sequence[message_model.Message]:
    return await base_repository.get_all(db=db, model=message_model.Message)


async def get_message_by_id(db: AsyncSession, id_value: int) -> Optional[message_model.Message]:
    return await base_repository.get_by_id(db=db, model=message_model.Message, id_value=id_value)


async def get_messages_by_session(db: AsyncSession, session_id: int) -> Sequence[message_model.Message]:
    """Custom query — filters on a non-PK column, doesn't fit the generic shape."""
    stmt = select(message_model.Message).where(message_model.Message.session_id == session_id)
    result = await db.execute(stmt)
    return result.scalars().all()


async def create_message(db: AsyncSession, message: message_model.Message) -> message_model.Message:
    return await base_repository.create(db=db, instance=message)


async def update_message(db: AsyncSession, message: message_model.Message, data: dict) -> message_model.Message:
    return await base_repository.update(db=db, instance=message, data=data)


async def delete_message(db: AsyncSession, message: message_model.Message) -> None:
    await base_repository.delete_by_id(db=db, model=message_model.Message, id_value=message.id)


async def delete_all_messages(db: AsyncSession) -> None:
    await db.execute(sqlalchemy_delete(message_model.Message))
    await db.commit()