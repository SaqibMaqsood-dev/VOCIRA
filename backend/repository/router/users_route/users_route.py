from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc, or_
from sqlalchemy.orm import selectinload
from typing import List
from hashing.hashing import Hash
from schema import user_schema , message_schema
from models import user_model, role_model 
from database import database
from tokken.access_tokken.get_current_user import current_user
from core.config import settings
from fastapi import Request
from services.user_services.create_user import UserCreate
from services.session_services.session_create import SessionCreate
from fastapi import status



router = APIRouter(prefix="/users", tags=["Users"])


# ---------------- SIGNUP ----------------
@router.post('/signup', response_model=user_schema.ShowUser)
async def signup(
    request: user_schema.User,
    db: AsyncSession = Depends(database.get_db),
    # _=Depends(require_permission("user_create")
):

  new_user = await UserCreate(db=db , request=request)
  
  return new_user

# ---------------- GET USERS ----------------
@router.get("/get_user", response_model=List[user_schema.ShowUser])
async def getting_users(
    db: AsyncSession = Depends(database.get_db),
):

    result = await db.execute(
        select(user_model.Users)
        .options(selectinload(user_model.Users.role))
        .order_by(asc(user_model.Users.id))
    )
        
    users = result.scalars().all()

    if not users:
        raise HTTPException(404, "No users found")

    return users


# ---------------- GET USER BY ID ----------------
@router.get("/get_user_id/{id}", response_model=user_schema.ShowUser)
async def getting_users_by(
    id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: user_schema.User = Depends(current_user)
):

    result = await db.execute(
        select(user_model.Users)
        .options(selectinload(user_model.Users.role))
        .where(user_model.Users.id == id)
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(404, "User not found")

    if current_user.role.name != "admin" and current_user.id != id:
        raise HTTPException(403, "Not allowed")

    return user


# ---------------- DELETE USER ----------------
@router.delete("/delete_user/{id}")
async def delete_user(
    id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: user_schema.User = Depends(current_user)
):

    result = await db.execute(
        select(user_model.Users)
        .where(user_model.Users.id == id)
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(404, "User not found")

    if current_user.role.name != "admin" and current_user.id != id:
        raise HTTPException(403, "Not allowed")

    await db.delete(user)
    await db.commit()

    return {"message": f"user deleted with id {id}"}


# ---------------- UPDATE USER ----------------
@router.put("/update_data/{id}")
async def update_user(
    request: user_schema.User,
    id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: user_schema.User = Depends(current_user)
):

    result = await db.execute(
        select(user_model.Users)
        .where(user_model.Users.id == id)
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(404, "User not found")

    if current_user.role.name != "admin" and current_user.id != id:
        raise HTTPException(403, "Not allowed")

    user.name = request.name
    user.email = request.email
    user.password = Hash.get_hash_password(request.password)
    user.date_birth = request.date_birth
    user.phone_number = request.phone_number
    user.address = request.address
    user.location = request.location

    await db.commit()
    await db.refresh(user)

    return {"message": "user updated"}


# ---------------- PARTIAL UPDATE ----------------
@router.patch("/partial_update/{id}")
async def partial_update(
    request: user_schema.UserPartialUpdate,
    id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: user_schema.User = Depends(current_user)
):

    result = await db.execute(
        select(user_model.Users)
        .where(user_model.Users.id == id)
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(404, "User not found")

    if current_user.role.name != "admin" and current_user.id != id:
        raise HTTPException(403, "Not allowed")

    data = request.model_dump(exclude_unset=True)
    
    if "password" in data:
        data["password"] = Hash.get_hash_password(data["password"])

    for key, value in data.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)

    return {"message": "user updated", "updated_fields": data}


# ---------------- SEARCH USERS ----------------
@router.get("/search/{user_search}", response_model=List[user_schema.ShowUser])
async def search_users(
    user_search: str,
    db: AsyncSession = Depends(database.get_db),
    current_user: user_schema.User = Depends(current_user)
):

    result = await db.execute(
        select(user_model.Users)
        .where(
            or_(
                user_model.Users.email.ilike(f"%{user_search}%"),
                user_model.Users.name.ilike(f"%{user_search}%")
            )
        )
    )
    
    users = result.scalars().all()

    if not users:
        raise HTTPException(404, "No matching users found")

    return users

# ---------------- Live-kit ----------------

from services.livekit.livekit_service import LivekitServices
import random

@router.post("/live_kit/token", response_model=user_schema.TokkenResponse)
async def room_tokken(
    db: AsyncSession = Depends(database.get_db),
    current_user: user_schema.User = Depends(current_user),
):  
    stmt = (
        select(user_model.Users)
        .options(selectinload(user_model.Users.role))
        .where(user_model.Users.id == current_user.user_id)
    )
    
    result = await db.execute(stmt)
    user_record = result.scalar_one_or_none()
    
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found")

    # 1. Create session and extract dictionary payload
    session_data = await SessionCreate.session_create(users_id=current_user.user_id)
    
    if session_data and "session_id" in session_data:
        real_session_id = session_data["session_id"]
        
        room = f"room-{real_session_id}" 
        
        livekit = LivekitServices(
            user_id=current_user.user_id,
            user_role=user_record.role.value if hasattr(user_record.role, "value") else str(user_record.role),
        )

        token = livekit.livekit_token(
            api_key=settings.API_KEY,
            api_secret=settings.API_SECRET,
            room_name=room,
            user_name=user_record.name
        )
        
        return user_schema.TokkenResponse(
            tokken=token,
            room=room,
            url=settings.LIVEKIT_URL
        )

    else:
        raise HTTPException(
            status_code=500, detail="Failed to initiate voice backend infrastructure session token."
        )



@router.post("/guest/live_kit/token")
async def room_tokken(
    db: AsyncSession = Depends(database.get_db),
):
    session_data = await SessionCreate.session_create(users_id=None)

    # Safety check: Ensure session data was created successfully
    if not session_data or "session_id" not in session_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize a guest session tracking space."
        )
        
    session_id = session_data["session_id"]
    generated_room_name = f"room-{session_id}"
   
    livekit = LivekitServices(
        user_id=None,
        user_role="guest",
    )
    
    token = livekit.livekit_token(
        api_key=settings.API_KEY,      
        api_secret=settings.API_SECRET, 
        room_name=generated_room_name,
        user_name="guest"
    )
    
    return user_schema.TokkenResponse(
        tokken=token,
        room=generated_room_name,
        url=settings.LIVEKIT_URL
    )