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
import uuid

async def UserCreate(db : AsyncSession, request):

    # check existing user
    result = await db.execute(
        select(user_model.Users).where(user_model.Users.email == request.email)
    )

    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(400, "User already exists")

    # get role
    role_result = await db.execute(
        select(role_model.Role).where(role_model.Role.name == request.role)
    )

    role_obj = role_result.scalar_one_or_none()

    if not role_obj:
        raise HTTPException(400, "Role not found")

    # ------------------------
    # GUEST USER LOGIC
    # ------------------------
    if role_obj.name == "guest":

        new_user = user_model.Users(
            name=f"guest_{uuid.uuid4().hex[:8]}",
            email=f"guest_{uuid.uuid4().hex[:8]}@guest.local",
            password=None,
            role_id=role_obj.role_id,
            date_birth=None,
            phone_number=None,
            address=None,
            location=None
        )

    # ------------------------
    # NORMAL USER LOGIC
    # ------------------------
    else:
            
        hashed_pass = Hash.get_hash_password(request.password)

        new_user = user_model.Users(
            name=request.name,
            email=request.email,
            password=hashed_pass,
            role_id=role_obj.role_id,
            date_birth=request.date_birth,
            phone_number=request.phone_number,
            address=request.address,
            location=request.location
        )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user