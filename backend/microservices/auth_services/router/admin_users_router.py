"""
Managing parent accounts - for the admin panel.

Why this was needed:

VOCIRA's own accounts (muhmmadahmed763@edu.com and the like) live in
Postgres, not in ERPNext. And there was NO way to see or change them
- no page in the admin panel, no endpoint to change a password, no
"forgot password". Everything meant reaching for psql or a script.

This router fills that gap.

Why it sits in the AUTH service rather than livekit:

Password hashing uses pwdlib + argon2, which only exists in the auth
service's venv (the import fails outright in livekit's venv). Beyond
that, the auth service is where users live - managing them from there
is the right place.

The gateway forwards /auth/{path} to this service, so the panel's
route becomes /auth/admin/users.
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

    # The ERPNext Guardian record (EDU-GRD-...). Without it the
    # account is still created, but it reaches no child.
    parent_id: Optional[str] = Field(default=None, max_length=100)
    role: str = Field(default="guardian")


class UserUpdate(BaseModel):
    # Changing the email changes the login - the old one stops
    # working. This is allowed deliberately: a parent's address can
    # change, or it may need to match the ERPNext record.
    email: Optional[EmailStr] = None
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
    # password_hashed never leaves the service - nothing needs it,
    # and sending it out is just a way to leak it by accident.
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

    print(f"[Admin] account created: {email} -> {user.parent_id}")

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

    if request.email is not None:
        email = str(request.email).strip().lower()

        if email != user.email:
            # Taking over another account's email would leave two
            # accounts on the same address, with nothing to decide
            # which one the login belongs to.
            taken = (
                await db.execute(
                    select(Users).where(
                        Users.email == email,
                        Users.user_id != user_id,
                    )
                )
            ).scalar_one_or_none()

            if taken is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Another account already uses {email}",
                )

            print(f"[Admin] email changed: {user.email} -> {email}")
            user.email = email

    if request.name is not None:
        user.name = request.name.strip()

    if request.parent_id is not None:
        # Sending it empty means unlinking. So "" becomes None -
        # otherwise an empty string reaches the DB and matches no
        # guardian in ERPNext.
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

    print(f"[Admin] account update: {user.email}")

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

    The old password is not asked for - this is the admin path, and
    its whole purpose is to let the school help a parent who has
    forgotten theirs.
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

    print(f"[Admin] password reset: {user.email}")

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

    # Deleting your own account locks you out of the panel with no
    # way back in.
    if str(user.user_id) == str(getattr(admin, "user_id", "")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    email = user.email
    await db.delete(user)
    await db.commit()

    print(f"[Admin] account deleted: {email}")

    return {"deleted": True, "email": email}
