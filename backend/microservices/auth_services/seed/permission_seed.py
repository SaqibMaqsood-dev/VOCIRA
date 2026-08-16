from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.microservices.auth_services.models.permission_model import Permission

USER_PERMISSIONS = [
    "user.create",
    "user.read",
    "user.read_single",
    "user.update",
    "user.partial_update",
    "user.delete",
    "user.search",
]

SESSION_PERMISSIONS = [
    "session.create",
    "session.read",
    "session.read_single",
    "session.update",
    "session.delete",
]

MESSAGE_PERMISSIONS = [
    "message.send",
    "message.read",
    "message.read_single",
    "message.update",
    "message.delete",
]

ALL_PERMISSIONS = (
    USER_PERMISSIONS
    + SESSION_PERMISSIONS
    + MESSAGE_PERMISSIONS
)


async def Permission_Seeding(db: AsyncSession):

    result = await db.execute(select(Permission.name))
    existing_permissions = result.scalars().all()

    new_permissions = [
        Permission(name=permission)
        for permission in ALL_PERMISSIONS
        if permission not in existing_permissions
    ]

    if new_permissions:
        db.add_all(new_permissions)
        await db.commit()

        print(
            f"Permissions Added: {[p.name for p in new_permissions]}"
        )
    else:
        print("Permissions already seeded.")