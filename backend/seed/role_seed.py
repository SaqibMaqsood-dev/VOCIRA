from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.role_model import Role

DEFAULT_ROLES = ["admin", "user", "guest"]


async def seed_roles(db: AsyncSession):

    # fetch existing roles
    result = await db.execute(select(Role.name))
    existing_roles = set(result.scalars().all())

    # prepare missing roles
    new_roles = [
        Role(name=role_name)
        for role_name in DEFAULT_ROLES
        if role_name not in existing_roles
    ]

    # insert only if needed
    if new_roles:
        db.add_all(new_roles)
        await db.commit()
        print(f"Added roles: {[r.name for r in new_roles]}")
        print("role seed")
        
