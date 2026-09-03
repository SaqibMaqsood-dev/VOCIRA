from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.helper_functions.database import get_db
from backend.microservices.livekit_Rag_services.schema import message_schema
from backend.microservices.livekit_Rag_services.services.router_services.message_service import MessageService 

router = APIRouter(prefix="/messages", tags=["Messages"])

message_service = MessageService()


@router.get(
    "/get_message",
    response_model=List[message_schema.MessageResponse]
)
async def get_messages(
    limit: int,
    skip: int,
    db: AsyncSession = Depends(get_db)
):
    return await message_service.get_all_messages(
        db=db,
        limit=limit,
        skip=skip
    )


@router.get(
    "/{id}",
    response_model=message_schema.MessageResponse
)
async def get_message_by_id(
    id: int,
    db: AsyncSession = Depends(get_db)
):
    return await message_service.get_message_by_id(
        db=db,
        id_value=id
    )
    

@router.get(
    "/session/{session_id}",
    response_model=List[message_schema.MessageResponse]
)
async def get_messages_by_session(
    session_id: int,
    db: AsyncSession = Depends(get_db)
):
    return await message_service.get_messages_by_session(
        db=db,
        session_id=session_id
    )


@router.delete("/{id}")
async def delete_message(
    id: int,
    db: AsyncSession = Depends(get_db)
):
    return await message_service.delete_message(
        db=db,
        id_value=id
    )


@router.put("/{id}")
async def update_message(
    request: message_schema.MessageCreate,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    return await message_service.update_message(
        db=db,
        id_value=id,
        request=request
    )


@router.patch("/{id}")
async def partial_update_message(
    request: message_schema.MessagePartialUpdate,
    id: int,
    db: AsyncSession = Depends(get_db)
):
    return await message_service.partial_update_message(
        db=db,
        id_value=id,
        request=request
    )


@router.delete("/messages/delete_all")
async def delete_all_messages(
    db: AsyncSession = Depends(get_db)
):
    return await message_service.delete_all_messages(db=db)

