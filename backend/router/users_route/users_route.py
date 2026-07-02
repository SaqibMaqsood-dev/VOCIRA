from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from schema import user_schema
from database import database
from tokken.access_tokken.get_current_user import current_user
from services.user_services.user_logic import (
    get_all_users,
    get_user_by_id,
    delete_user,
    update_user_full,
    update_user_partial,
    search_users,
    create_user_room_token,
    create_guest_room_token,
    UserCreate
)

router = APIRouter(prefix="/users", tags=["Users"])


# ---------------- SIGNUP ----------------
@router.post('/signup', response_model=user_schema.ShowUser)
async def signup(
    request: user_schema.User,
    db: AsyncSession = Depends(database.get_db),
):
    return await UserCreate(db=db, request=request)


# ---------------- GET USERS ----------------
@router.get("/get_user", response_model=List[user_schema.ShowUser])
async def getting_users(db: AsyncSession = Depends(database.get_db)):
    return await get_all_users(db=db)


# ---------------- GET USER BY ID ----------------
@router.get("/get_user_id/{id}", response_model=user_schema.ShowUser)
async def getting_users_by(
    id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: user_schema.User = Depends(current_user)
):
    return await get_user_by_id(db=db, id_value=id, current_user=current_user)


# ---------------- DELETE USER ----------------
@router.delete("/delete_user/{id}")
async def delete_user_route(
    id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: user_schema.User = Depends(current_user)
):
    return await delete_user(db=db, id_value=id, current_user=current_user)


# ---------------- UPDATE USER ----------------
@router.put("/update_data/{id}")
async def update_user_route(
    request: user_schema.User,
    id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: user_schema.User = Depends(current_user)
):
    return await update_user_full(db=db, id_value=id, request=request, current_user=current_user)


# ---------------- PARTIAL UPDATE ----------------
@router.patch("/partial_update/{id}")
async def partial_update_route(
    request: user_schema.UserPartialUpdate,
    id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: user_schema.User = Depends(current_user)
):
    return await update_user_partial(db=db, id_value=id, request=request, current_user=current_user)


# ---------------- SEARCH USERS ----------------
@router.get("/search/{user_search}", response_model=List[user_schema.ShowUser])
async def search_users_route(
    user_search: str,
    db: AsyncSession = Depends(database.get_db),
    current_user: user_schema.User = Depends(current_user)
):
    return await search_users(db=db, search_term=user_search)


# ---------------- LIVEKIT ----------------
@router.post("/live_kit/token", response_model=user_schema.TokkenResponse)
async def room_token(
    db: AsyncSession = Depends(database.get_db),
    current_user: user_schema.User = Depends(current_user),
):
    return await create_user_room_token(db=db, current_user=current_user)


@router.post("/guest/live_kit/token", response_model=user_schema.TokkenResponse)
async def guest_room_token():
    return await create_guest_room_token()