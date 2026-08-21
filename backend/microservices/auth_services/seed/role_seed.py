from sqlalchemy import select

from backend.microservices.auth_services.models.role_model import Role

async def role_seeding(db):
    roles = [
        {"role_id": "ROLE-001", "name": "admin"},
        {"role_id": "ROLE-002", "name": "guardian"},
        {"role_id": "ROLE-003", "name": "guest"},
    ]

    try:
        for role_data in roles:
            result = await db.execute(
                select(Role).where(Role.role_id == role_data["role_id"])
            )

            existing_role = result.scalar_one_or_none()

            if existing_role:
                print(f"Role already exists: {role_data['role_id']}")
                continue

            db.add(Role(**role_data))
            print(f"Added role: {role_data['role_id']}")

        await db.commit()
        print("Roles seeded successfully.")

    except Exception:
        await db.rollback()
        raise