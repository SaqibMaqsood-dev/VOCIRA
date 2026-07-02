from typing import Optional, Sequence

from sqlalchemy import select, asc, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from models import user_model , role_model
from repository import base_repository

# Reusable eager-load option — almost every user query in this app needs the role relationship
WITH_ROLE = [selectinload(user_model.Users.role)]


async def get_all_users(db: AsyncSession) -> Sequence[user_model.Users]:
    return await base_repository.get_all(
        db=db,
        model=user_model.Users,
        options=WITH_ROLE,
        order_by=asc(user_model.Users.id),
    )


async def get_user_by_id(db: AsyncSession, id_value: int) -> Optional[user_model.Users]:
    return await base_repository.get_by_id(
        db=db,
        model=user_model.Users,
        id_value=id_value,
        options=WITH_ROLE,
    )


async def delete_user(db: AsyncSession, user: user_model.Users) -> None:
    await db.delete(user)
    await db.commit()


async def update_user_full(db: AsyncSession, user: user_model.Users, data: dict) -> user_model.Users:
    return await base_repository.update(db=db, instance=user, data=data)


async def update_user_partial(db: AsyncSession, user: user_model.Users, data: dict) -> user_model.Users:
    return await base_repository.update(db=db, instance=user, data=data)


async def search_users(db: AsyncSession, search_term: str) -> Sequence[user_model.Users]:
    """Custom query — not generic, since it filters across two specific columns with OR/ilike."""
    stmt = select(user_model.Users).where(
        or_(
            user_model.Users.email.ilike(f"%{search_term}%"),
            user_model.Users.name.ilike(f"%{search_term}%"),
        )
    )
    result = await db.execute(stmt)
    return result.scalars().all()



async def get_user_by_email(db: AsyncSession, email: str) -> Optional[user_model.Users]:
    stmt = select(user_model.Users).where(user_model.Users.email == email)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_role_by_name(db: AsyncSession, name: str):
    stmt = select(role_model.Role).where(role_model.Role.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()