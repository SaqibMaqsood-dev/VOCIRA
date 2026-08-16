import asyncio

from backend.helper_functions.database import SessionLocal
from backend.microservices.auth_services.seed import (
    Permission_Seeding,
    role_seeding,
    roles_permissions,
)


async def running_seed():
    async with SessionLocal() as db:
        await Permission_Seeding(db)
        await role_seeding(db)
        await roles_permissions(db)


if __name__ == "__main__":
    asyncio.run(running_seed())