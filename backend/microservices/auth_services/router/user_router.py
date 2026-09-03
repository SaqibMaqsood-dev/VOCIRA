from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, Header, HTTPException, status
from backend.microservices.auth_services.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.microservices.auth_services.models.user_model import Users
from backend.helper_functions.database import get_db
from backend.microservices.auth_services import schema as user_schema
from backend.microservices.auth_services.db import get_db
from backend.microservices.auth_services.schema import user_schema
from backend.microservices.auth_services.services.router_services.user_service import UserServices
from backend.helper_functions.token_service.access_tokken.get_current_user import (
current_user
)

from backend.microservices.auth_services.schema import (
    user_schema,
    
)




router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

user_service = UserServices()

# ---------------- SIGNUP ----------------

@router.post(
    "/signup",
    response_model=user_schema.ShowUser,
)

async def signup(
    request: user_schema.User,
    db: AsyncSession = Depends(get_db),
):
    return await user_service.UserCreate(
        request=request,
        db=db,
    )


# ---------------- GET ALL USERS ----------------

@router.get(
    "/",
    response_model=List[user_schema.ShowUser],
)
async def get_users(
    limit: int = 10,
    skip: int = 0,
    db: AsyncSession = Depends(get_db),
):
    return await user_service.get_all_users(
        db = db,
        limit=limit,
        skip=skip
        )


# ---------------- GET USER ----------------

@router.get(
    "/{id}",
    response_model=user_schema.ShowUser,
)
async def get_user(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: user_schema.ShowUser = Depends(current_user),
):
    return await user_service.get_user(
        user_id=id,
        db=db,
    )


# ---------------- DELETE USER ----------------

@router.delete(
    "/{id}",
)
async def delete_user(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: user_schema.ShowUser = Depends(current_user),
):
    return await user_service.delete_user(
        user_id=id,
        db=db,
    )


# ---------------- UPDATE USER ----------------

@router.put(
    "/{id}",
)

async def update_user(
    id: UUID,
    request: user_schema.UpdateUser,
    db: AsyncSession = Depends(get_db),
    current_user: user_schema.ShowUser = Depends(current_user),
):

    data = {
        "name": request.name,
        "role": request.role,
        "email": request.email,
        "password_hashed": request.password,
        "phone_number": request.phone_number,
        "location": request.location,
        "address": request.address,
        "date_birth": request.date_birth,
    }

    return await user_service.update_user(
        data=data,
        user_id=id,
        db=db
    )



# ---------------- PARTIAL UPDATE ----------------

@router.patch(
    "/{id}",
    response_model=user_schema.UserPartialUpdate,
)
async def partial_update(
    id: UUID,
    request: user_schema.UserPartialUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: user_schema.ShowUser = Depends(current_user),
):
    return await user_service.user_partialy_update(
        user_id=id,
        request=request,
        db=db,
    )


# ---------------- SEARCH USERS ----------------

@router.get(
    "/search/{keyword}",
    response_model=List[user_schema.ShowUser],
)
async def search_users(
    keyword: str,
    db: AsyncSession = Depends(get_db),
    current_user: user_schema.ShowUser = Depends(current_user),
):
    return await user_service.search_users(
        keyword=keyword,
        db=db,
    )



# ---------------- INTERNAL USER ----------------



from uuid import UUID


@router.get(
    "/internal/{user_id}",
    response_model=user_schema.InternalUserResponse,
)
async def get_internal_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    x_internal_key: str | None = Header(default=None),
):
    # Ye endpoint kisi bhi user ka role aur ERP parent_id deta hai -
    # yaani ERP authorization ki chabi. Pehle bilkul khula tha.
    # Ye service-to-service call hai (JWT ke baghair aati hai),
    # is liye shared secret se protect kiya gaya hai.
    if x_internal_key != settings.INTERNAL_SERVICE_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service key",
        )

    result = await db.execute(
        select(Users)
        .options(selectinload(Users.role))
        .where(Users.user_id == user_id)
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return {
        "user_id": user.user_id,
        "parent_id": user.parent_id,
        "role": user.role.name if user.role else None,
    }