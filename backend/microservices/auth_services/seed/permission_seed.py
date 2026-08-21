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

    result = await db.execute(
        select(Permission.name)
    )

    existing_permissions = set(
        result.scalars().all()
    )

    new_permissions = []

    for index, permission_name in enumerate(
        ALL_PERMISSIONS,
        start=1,
    ):

        if permission_name in existing_permissions:
            continue

        permission = Permission(
            permission_id=f"PERMISSION-{index:03d}",
            name=permission_name,
        )

        new_permissions.append(permission)

    if new_permissions:

        db.add_all(new_permissions)

        await db.commit()

        print(
            f"Permissions Added: "
            f"{[p.name for p in new_permissions]}"
        )

    else:

        print("Permissions already seeded.")
