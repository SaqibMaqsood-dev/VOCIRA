"""
Parents ke accounts sambhalne ke liye - admin panel ke waaste.

Kyun zaroori tha:

VOCIRA ke apne accounts (ahmed@test.com waghera) Postgres mein hain,
ERPNext mein nahi. Aur unhein dekhne ya badalne ka KOI raasta nahi
tha - na admin panel mein koi page, na password badalne ka endpoint,
na "forgot password". Har cheez ke liye psql ya koi script chalani
parti thi.

Ye router us kami ko poora karta hai.

Ye AUTH service mein kyun hai, livekit mein nahi:

Password hashing pwdlib + argon2 se hoti hai, aur wo sirf auth
service ke venv mein mojood hai (livekit ke venv mein import hi
fail ho jata hai). Us se hat kar bhi, users ka ghar auth service
hi hai - unhein wahin se sambhalna theek hai.

Gateway /auth/{path} ko is service par bhejta hai, is liye panel
ke liye raasta /auth/admin/users banta hai.
"""

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.helper_functions.database.session import get_db
from backend.helper_functions.token_service.access_tokken.require_admin import (
    require_admin,
)
from backend.microservices.auth_services.models.role_model import Role
from backend.microservices.auth_services.models.user_model import Users
from backend.microservices.auth_services.services.hashing_service.hashing import (
    Hash,
)


router = APIRouter(
    prefix="/admin/users",
    tags=["Admin - Users"],
    dependencies=[Depends(require_admin)],
)


MIN_PASSWORD = 8


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=MIN_PASSWORD, max_length=128)

    # ERPNext ka Guardian record (EDU-GRD-...). Is ke baghair account
    # ban to jayega magar us ko koi bachcha nahi milega.
    parent_id: Optional[str] = Field(default=None, max_length=100)
    role: str = Field(default="guardian")


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    parent_id: Optional[str] = Field(default=None, max_length=100)
    role: Optional[str] = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=MIN_PASSWORD, max_length=128)


async def _role_id(db: AsyncSession, name: str) -> str:
    row = (
        await db.execute(select(Role).where(Role.name == name.strip().lower()))
    ).scalar_one_or_none()

    if row is None:
        available = [
            r.name for r in (await db.execute(select(Role))).scalars().all()
        ]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown role '{name}'. Available: {', '.join(available)}",
        )

    return row.role_id


def _shape(user: Users, role_name: str | None) -> dict:
    # password_hashed kabhi bahar nahi jata - us ki koi zaroorat nahi
    # aur wo bahar bhejna ghalti se leak hone ka raasta banata hai.
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "name": user.name,
        "parent_id": user.parent_id,
        "role": role_name,
        "created_at": (
            user.created_at.isoformat(timespec="seconds")
            if user.created_at
            else None
        ),
    }


# =========================================================
# LIST
# =========================================================

@router.get("")
async def list_users(db: AsyncSession = Depends(get_db)):
    """Saare accounts, role ke naam ke sath."""

    rows = (
        await db.execute(
            select(Users, Role.name)
            .outerjoin(Role, Role.role_id == Users.role_id)
            .order_by(Users.created_at.desc())
        )
    ).all()

    users = [_shape(user, role) for user, role in rows]

    return {
        "users": users,
        "total": len(users),
        "linked": sum(1 for u in users if u["parent_id"]),
    }


# =========================================================
# ROLES  (form ke dropdown ke liye)
# =========================================================

@router.get("/roles")
async def list_roles(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Role).order_by(Role.name))).scalars().all()
    return [{"role_id": r.role_id, "name": r.name} for r in rows]


# =========================================================
# NAYA ACCOUNT
# =========================================================

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    request: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    email = str(request.email).strip().lower()

    exists = (
        await db.execute(select(Users).where(Users.email == email))
    ).scalar_one_or_none()

    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An account with {email} already exists",
        )

    role_id = await _role_id(db=db, name=request.role)

    user = Users(
        user_id=uuid.uuid4(),
        email=email,
        name=request.name.strip(),
        parent_id=(request.parent_id or "").strip() or None,
        role_id=role_id,
        password_hashed=Hash.get_hash_password(request.password),
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    print(f"👤 [Admin] account bana: {email} -> {user.parent_id}")

    return _shape(user, request.role.strip().lower())


# =========================================================
# BADALNA
# =========================================================

@router.patch("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    request: UserUpdate,
    db: AsyncSession = Depends(get_db),
):
    user = (
        await db.execute(select(Users).where(Users.user_id == user_id))
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if request.name is not None:
        user.name = request.name.strip()

    if request.parent_id is not None:
        # Khali bhejna = link hatana. Is liye "" ko None kar dete hain,
        # warna khali string DB mein chali jati aur wo ERPNext mein
        # kisi guardian se mel nahi khati.
        user.parent_id = request.parent_id.strip() or None

    role_name = None

    if request.role is not None:
        user.role_id = await _role_id(db=db, name=request.role)
        role_name = request.role.strip().lower()

    await db.commit()
    await db.refresh(user)

    if role_name is None:
        role_name = (
            await db.execute(
                select(Role.name).where(Role.role_id == user.role_id)
            )
        ).scalar_one_or_none()

    print(f"👤 [Admin] account update: {user.email}")

    return _shape(user, role_name)


# =========================================================
# PASSWORD RESET
# =========================================================

@router.post("/{user_id}/password")
async def reset_password(
    user_id: uuid.UUID,
    request: PasswordReset,
    db: AsyncSession = Depends(get_db),
):
    """
    Naya password set karein.

    Purana password nahi maanga jata - ye admin ka raasta hai, jis
    ka maqsad hi ye hai ke parent apna password bhool jaye to school
    us ki madad kar sake.
    """

    user = (
        await db.execute(select(Users).where(Users.user_id == user_id))
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.password_hashed = Hash.get_hash_password(request.password)
    await db.commit()

    print(f"🔑 [Admin] password reset: {user.email}")

    return {"updated": True, "email": user.email}


# =========================================================
# HATANA
# =========================================================

@router.delete("/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: Annotated[object, Depends(require_admin)] = None,
):
    user = (
        await db.execute(select(Users).where(Users.user_id == user_id))
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Apna hi account hatane se panel se bahar ho jayenge aur andar
    # aane ka koi raasta nahi bachega.
    if str(user.user_id) == str(getattr(admin, "user_id", "")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    email = user.email
    await db.delete(user)
    await db.commit()

    print(f"🗑️ [Admin] account hataya: {email}")

    return {"deleted": True, "email": email}
