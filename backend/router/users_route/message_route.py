from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import database
from schema import message_schema
from services.message_services import message_logic

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.get("/get_message", response_model=List[message_schema.MessageResponse])
async def get_messages(db: AsyncSession = Depends(database.get_db)):
    return await message_logic.get_all_messages(db=db)


@router.get("/{id}", response_model=message_schema.MessageResponse)
async def get_message_by_id(id: int, db: AsyncSession = Depends(database.get_db)):
    return await message_logic.get_message_by_id(db=db, id_value=id)


@router.get("/session/{session_id}", response_model=List[message_schema.MessageResponse])
async def get_messages_by_session(session_id: int, db: AsyncSession = Depends(database.get_db)):
    return await message_logic.get_messages_by_session(db=db, session_id=session_id)


@router.delete("/{id}")
async def delete_message(id: int, db: AsyncSession = Depends(database.get_db)):
    return await message_logic.delete_message(db=db, id_value=id)


@router.put("/{id}")
async def update_message(
    request: message_schema.MessageCreate,
    id: int,
    db: AsyncSession = Depends(database.get_db)
):
    return await message_logic.update_message(db=db, id_value=id, request=request)


@router.patch("/{id}")
async def partial_update_message(
    request: message_schema.MessagePartialUpdate,
    id: int,
    db: AsyncSession = Depends(database.get_db)
):
    return await message_logic.partial_update_message(db=db, id_value=id, request=request)


@router.delete("/messages/delete_all")
async def delete_all_messages(db: AsyncSession = Depends(database.get_db)):
    return await message_logic.delete_all_messages(db=db)