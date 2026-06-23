from sqlalchemy import select
from models.role_model import Role
from models.permision_model import Permission
from models.role_permission_model import role_permissions
from sqlalchemy.ext.asyncio import AsyncSession


ROLE_PERMISSIONS_MAP = {
    "admin": "*",
    "user": [
        "user.read_single",
        "session.create",
        "message.send",
        "user.search",
        "session.create",
        "message.send"
    ],
    
    "guest": [
        "session.create",
        "message.send",
        "user.search",
        "session.create",
        "message.send"
    ]
}


async def role_permission_seed(db: AsyncSession):

    # 1. Roles
    roles = (await db.execute(select(Role))).scalars().all()
    role_map = {r.name: r for r in roles}
        
    # 2. Permissions
    permissions = (await db.execute(select(Permission))).scalars().all()
    perm_map = {p.name: p for p in permissions}

    # 3. Existing mappings
    existing_rows = (await db.execute(select(role_permissions))).scalars().all()

    existing_set = {
        (row.role_id, row.permission_id)
        for row in existing_rows
    }

    # 4. Assign permissions
    for role_name, perms in ROLE_PERMISSIONS_MAP.items():

        role = role_map.get(role_name)
        if not role:
            continue

        # ADMIN → all permissions
        if perms == "*":
            for perm in permissions:
                key = (role.role_id, perm.id)

                if key not in existing_set:
                    db.add(role_permissions(
                        role_id=role.role_id,
                        permission_id=perm.id
                    ))

                    existing_set.add(key)

            continue

        # NORMAL ROLES
        for perm_name in perms:
            perm = perm_map.get(perm_name)
            if not perm:
                continue

            key = (role.role_id, perm.id)

            if key not in existing_set:
                db.add(role_permissions(
                    role_id=role.role_id,
                    permission_id=perm.id
                ))

                existing_set.add(key)

    await db.commit()

    print("Role-permission seed completed")