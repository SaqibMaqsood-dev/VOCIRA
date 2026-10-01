"""
Admin user banayein (ya password reset karein).

    python create_admin.py                                  # default: admin@vocira.com (The Educators)
    python create_admin.py <email> <password>               # The Educators ka admin
    python create_admin.py <email> <password> --school demo-b   # kisi aur school ka admin
    python create_admin.py <email> <password> --super       # platform super admin (koi school nahi)

Admin panel ke saare endpoints `require_admin` ke peeche hain, aur
role JWT se aata hai - is liye login admin role wale user se hona
zaroori hai. School admin sirf apne school ka data dekhta hai (/admin);
super admin schools add/remove karta hai (/superadmin).
"""
import asyncio
import sys
import uuid

from sqlalchemy import select, text

from backend.helper_functions.database.session import SessionLocal
from backend.microservices.auth_services.models.role_model import Role
from backend.microservices.auth_services.models.user_model import Users
from backend.microservices.auth_services.services.hashing_service.hashing import Hash

BUILT_IN_SCHOOLS = {"educators", "demo-b"}   # services/tenants.py

args = sys.argv[1:]
SUPER = "--super" in args
SCHOOL = None
if "--school" in args:
    at = args.index("--school")
    if at + 1 >= len(args):
        sys.exit("!! --school ke baad school id likhein, maslan: --school demo-b")
    SCHOOL = args[at + 1]
    del args[at:at + 2]
args = [a for a in args if a != "--super"]

if SUPER and SCHOOL:
    sys.exit("!! super admin kisi school ka nahi hota - --super ya --school, dono nahi")
if SUPER and len(args) < 2:
    sys.exit("!! super admin ke liye email aur apna password dein: python create_admin.py <email> <password> --super")

EMAIL = args[0] if len(args) > 0 else "admin@vocira.com"
PASSWORD = args[1] if len(args) > 1 else "Admin@1234"
ROLE = "super_admin" if SUPER else "admin"


async def main():
    async with SessionLocal() as db:
        if SCHOOL and SCHOOL not in BUILT_IN_SCHOOLS:
            added = await db.scalar(text("SELECT 1 FROM schools WHERE id = :id"), {"id": SCHOOL})
            if not added:
                print(f"!! school '{SCHOOL}' nahi mila - pehle /superadmin/schools se add karein")
                return

        role = (
            await db.execute(select(Role).where(Role.name == ROLE))
        ).scalar_one_or_none()
        if role is None:
            print(f"!! '{ROLE}' role DB mein nahi mila - auth service ek dafa chala lein (wo role bana deta hai)")
            return

        user = (
            await db.execute(select(Users).where(Users.email == EMAIL))
        ).scalar_one_or_none()
        if user is None:
            user = Users(
                user_id=uuid.uuid4(),
                name="Vocira Super Admin" if SUPER else "Vocira Admin",
                email=EMAIL,
                role_id=role.role_id,
                password_hashed=Hash.get_hash_password(PASSWORD),
                school_id=SCHOOL,
            )
            db.add(user)
            action = "bana diya"
        else:
            user.role_id = role.role_id
            user.password_hashed = Hash.get_hash_password(PASSWORD)
            user.school_id = SCHOOL
            action = "update kar diya"
        await db.commit()

    print(f"  {ROLE} {action}")
    print(f"    email    : {EMAIL}")
    print(f"    password : {PASSWORD}")
    if SUPER:
        print(f"    panel    : http://localhost:3000/superadmin")
    else:
        print(f"    school   : {SCHOOL or 'educators'}")
        print(f"    panel    : http://localhost:3000/admin")


asyncio.run(main())
