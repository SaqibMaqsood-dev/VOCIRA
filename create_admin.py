"""
Admin user banayein (ya password reset karein).

    python create_admin.py                     # default: admin@vocira.com
    python create_admin.py <email> <password>

Admin panel ke saare endpoints `require_admin` ke peeche hain, aur
role JWT se aata hai - is liye login admin role wale user se hona
zaroori hai. Roles pehle se seed hain (admin / guardian / guest).
"""

import asyncio
import sys
import uuid

from sqlalchemy import select

from backend.helper_functions.database.session import SessionLocal
from backend.microservices.auth_services.models.role_model import Role
from backend.microservices.auth_services.models.user_model import Users
from backend.microservices.auth_services.services.hashing_service.hashing import Hash


EMAIL = sys.argv[1] if len(sys.argv) > 1 else "admin@vocira.com"
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else "Admin@1234"


async def main():
    async with SessionLocal() as db:

        role = (
            await db.execute(select(Role).where(Role.name == "admin"))
        ).scalar_one_or_none()

        if role is None:
            print("!! 'admin' role DB mein nahi mila - seed chalayein")
            return

        user = (
            await db.execute(select(Users).where(Users.email == EMAIL))
        ).scalar_one_or_none()

        if user is None:
            user = Users(
                user_id=uuid.uuid4(),
                name="Vocira Admin",
                email=EMAIL,
                role_id=role.role_id,
                password_hashed=Hash.get_hash_password(PASSWORD),
            )
            db.add(user)
            action = "bana diya"
        else:
            user.role_id = role.role_id
            user.password_hashed = Hash.get_hash_password(PASSWORD)
            action = "update kar diya"

        await db.commit()

    print(f"  admin {action}")
    print(f"    email    : {EMAIL}")
    print(f"    password : {PASSWORD}")
    print(f"    panel    : http://localhost:3000/admin")


asyncio.run(main())
