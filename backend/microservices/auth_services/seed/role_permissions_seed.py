from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.microservices.auth_services.models.role_model import Role
from backend.microservices.auth_services.models.permission_model import Permission
from backend.microservices.auth_services.models.role_permision_model import role_permissions


ROLE_PERMISSIONS_MAP = {
    "admin": "*",

    "user": [
        "user.read_single",
        "session.create",
        "message.send",
        "user.search",
    ],

    "guest": [
        "session.create",
        "message.send",
        "user.search",
    ],
}


async def roles_permissions(db: AsyncSession):

    # -----------------------------
    # Fetch roles
    # -----------------------------
    roles = (await db.execute(select(Role))).scalars().all()

    role_map = {
        role.name: role
        for role in roles
    }

    # -----------------------------
    # Fetch permissions
    # -----------------------------
    permissions = (
        await db.execute(select(Permission))
    ).scalars().all()

    perm_map = {
        permission.name: permission
        for permission in permissions
    }

    # -----------------------------
    # Existing role-permission rows
    # -----------------------------
    existing_rows = (
        await db.execute(select(role_permissions))
    ).scalars().all()

    existing_set = {
        (row.role_id, row.permission_id)
        for row in existing_rows
    }

    # -----------------------------
    # Assign permissions
    # -----------------------------
    for role_name, perms in ROLE_PERMISSIONS_MAP.items():

        role = role_map.get(role_name)

        if role is None:
            continue

        # Admin gets all permissions
        if perms == "*":

            for permission in permissions:

                key = (
                    role.role_id,
                    permission.permission_id,
                )

                if key not in existing_set:

                    db.add(
                        role_permissions(
                            role_id=role.role_id,
                            permission_id=permission.permission_id,
                        )
                    )

                    existing_set.add(key)

            continue

        # User / Guest permissions
        for perm_name in perms:

            permission = perm_map.get(perm_name)

            if permission is None:
                continue

            key = (
                role.role_id,
                permission.permission_id,
            )

            if key not in existing_set:

                db.add(
                    role_permissions(
                        role_id=role.role_id,
                        permission_id=permission.permission_id,
                    )
                )

                existing_set.add(key)

    await db.commit()

    print("Role-Permission seeding completed.")