from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.permision_model import Permission


USER_PERMISSIONS = [
    "user.create",
    "user.read",
    "user.read_single",
    "user.update",
    "user.partial_update",
    "user.delete",
    "user.search"
]

SESSION_PERMISSIONS = [
    "session.create",
    "session.read",
    "session.read_single",
    "session.update",
    "session.delete"
]

MESSAGE_PERMISSIONS = [
    "message.send",
    "message.read",
    "message.read_single",
    "message.update",
    "message.delete"
]

ALL_PERMISSIONS = USER_PERMISSIONS + SESSION_PERMISSIONS + MESSAGE_PERMISSIONS


async def permission_seed(db: AsyncSession):
    # Step 1: get existing permissions in ONE query
    result = await db.execute(select(Permission.name))
    existing = set(result.scalars().all())

    # Step 2: prepare new permissions only
    new_permissions = [
        Permission(name=perm)
        for perm in ALL_PERMISSIONS
        if perm not in existing
    ]

    # Step 3: bulk insert
    if new_permissions:
        db.add_all(new_permissions)

    await db.commit()

print("Running permission seed...")

