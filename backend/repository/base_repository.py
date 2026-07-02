from typing import TypeVar, Type, Optional, Sequence, Any
from sqlalchemy import select, delete as sqlalchemy_delete
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType")


async def get_by_id(
    db: AsyncSession,
    model: Type[ModelType],
    id_value: int,
    options: Optional[list] = None,
) -> Optional[ModelType]:
    """Fetch a single row by primary key. Works for any model with an `id` column."""
    stmt = select(model).where(model.id == id_value)
    if options:
        stmt = stmt.options(*options)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_all(
    db: AsyncSession,
    model: Type[ModelType],
    options: Optional[list] = None,
    order_by: Optional[Any] = None,
) -> Sequence[ModelType]:
    """Fetch all rows for a model, optionally ordered and with eager-load options."""
    stmt = select(model)
    if options:
        stmt = stmt.options(*options)
    if order_by is not None:
        stmt = stmt.order_by(order_by)
    result = await db.execute(stmt)
    return result.scalars().all()


async def create(db: AsyncSession, instance: ModelType) -> ModelType:
    """Persist a new model instance."""
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return instance


async def update(db: AsyncSession, instance: ModelType, data: dict) -> ModelType:
    """Apply a dict of field updates to an existing instance and persist."""
    for key, value in data.items():
        setattr(instance, key, value)
    await db.commit()
    await db.refresh(instance)
    return instance


async def delete_by_id(db: AsyncSession, model: Type[ModelType], id_value: int) -> bool:
    """Delete a row by primary key. Returns True if a row was deleted."""
    stmt = sqlalchemy_delete(model).where(model.id == id_value)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0