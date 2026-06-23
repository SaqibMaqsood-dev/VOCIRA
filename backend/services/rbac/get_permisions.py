from sqlalchemy import select
from sqlalchemy.orm import selectinload
from models.user_model import Users
from models.role_model import Role
from database.database import AsyncSession

    
async def get_user_permissions(db: AsyncSession, user_id: int):

    result = await db.execute(
        select(Users)
        .options(
            selectinload(Users.role).selectinload(Role.permissions)
        )
        .where(Users.id == user_id)
    )

    user = result.scalar_one_or_none()

    if not user or not user.role:
        return []

    return [perm.name for perm in user.role.permissions]