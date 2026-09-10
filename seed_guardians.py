"""
Demo ke guardian accounts - VOCIRA ke login jo ERPNext se juRe hain.

Kyun zaroori hai:

ERPNext mein teen guardians aur un ke bachche mojood thay, magar
VOCIRA mein login sirf muhmmadahmed763@edu.com ka tha. Yaani Bilal aur Sana
ke 4 bachchon ka data - attendance, grades, fees - kisi ke liye bhi
pahunch se bahar tha. Voice assistant un tak ja hi nahi sakta tha.

parent_id ERPNext ke Guardian record ka naam hai. VOCIRA usi se
tay karta hai ke kis parent ko kaunse bachche dikhane hain, is liye
wo theek hona zaroori hai - ghalat ID doosre khandaan ka data khol
degi.

Chalane ka tareeqa:
    uv run --project backend/microservices/auth_services python seed_guardians.py

Dobara chalane se koi nuqsan nahi - jo pehle se hain un ka link aur
password bas theek kar diya jata hai.
"""

import asyncio
import uuid

from sqlalchemy import select

from backend.helper_functions.database.session import SessionLocal
from backend.microservices.auth_services.models.user_model import Users
from backend.microservices.auth_services.services.hashing_service.hashing import Hash

GUARDIAN_ROLE = "ROLE-002"
PASSWORD = "Test@1234"

# email, naam, ERPNext ka Guardian record
PEOPLE = [
    ("muhmmadahmed763@edu.com", "Muhammad Ahmed", "EDU-GRD-2026-00002"),
    ("bilal.hussain@edu.com", "Bilal Hussain",  "EDU-GRD-2026-00003"),
    ("sana.tariq@edu.com",  "Sana Tariq",     "EDU-GRD-2026-00004"),
]


async def main():
    async with SessionLocal() as db:
        for email, name, parent_id in PEOPLE:
            row = (
                await db.execute(select(Users).where(Users.email == email))
            ).scalar_one_or_none()

            if row is None:
                db.add(
                    Users(
                        user_id=uuid.uuid4(),
                        email=email,
                        name=name,
                        parent_id=parent_id,
                        role_id=GUARDIAN_ROLE,
                        password_hashed=Hash.get_hash_password(PASSWORD),
                    )
                )
                print(f"  bana    {email:18} -> {parent_id}")
            else:
                row.name = name
                row.parent_id = parent_id
                row.role_id = GUARDIAN_ROLE
                row.password_hashed = Hash.get_hash_password(PASSWORD)
                print(f"  update  {email:18} -> {parent_id}")

        await db.commit()

    print(f"\n  Password sab ka: {PASSWORD}")


asyncio.run(main())
