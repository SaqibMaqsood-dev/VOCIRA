from sqlalchemy import select
from backend.helper_functions.database import SessionLocal
from backend.microservices.auth_services.models.role_model import Role
from sqlalchemy.ext.asyncio import AsyncSession
ROLES = ["admin", "user", "guest"]


async def role_seeding(db : AsyncSession):

   

        result = await db.execute(select(Role.name))
        existing_roles = set(result.scalars().all())

        new_roles = [
            Role(name=role)
            for role in ROLES
            if role not in existing_roles
        ]

        if new_roles:
            db.add_all(new_roles)
            await db.commit()

            print("Roles Seeded")

