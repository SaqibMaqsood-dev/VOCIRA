from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from models import message_model
from repository import message_repository


async def get_all_messages(db: AsyncSession):
    messages = await message_repository.get_all_messages(db=db)
    if not messages:
        raise HTTPException(404, "No messages found")
    return messages


async def get_message_by_id(db: AsyncSession, id_value: int):
    message = await message_repository.get_message_by_id(db=db, id_value=id_value)
    if not message:
        raise HTTPException(404, f"No message found with id {id_value}")
    return message


async def get_messages_by_session(db: AsyncSession, session_id: int):
    messages = await message_repository.get_messages_by_session(db=db, session_id=session_id)
    if not messages:
        raise HTTPException(404, f"No messages found for session {session_id}")
    return messages


async def update_message(db: AsyncSession, id_value: int, request):
    message = await message_repository.get_message_by_id(db=db, id_value=id_value)
    if not message:
        raise HTTPException(404, f"No message found with id {id_value}")

    # NOTE: preserved original behavior — replaces fields rather than mutating in place
    data = {
        "sender_type": request.sender_type,
        "intent": "text",
        "source_type": request.source_type,
        "content": request.content,
    }
    await message_repository.update_message(db=db, message=message, data=data)
    return {"message": "Message updated successfully"}


async def partial_update_message(db: AsyncSession, id_value: int, request):
    message = await message_repository.get_message_by_id(db=db, id_value=id_value)
    if not message:
        raise HTTPException(404, f"No message found with id {id_value}")

    data = request.model_dump(exclude_unset=True)
    await message_repository.update_message(db=db, message=message, data=data)
    return {"message": "Message partially updated", "updated_fields": data}


async def delete_message(db: AsyncSession, id_value: int):
    message = await message_repository.get_message_by_id(db=db, id_value=id_value)
    if not message:
        raise HTTPException(404, f"No message found with id {id_value}")

    await message_repository.delete_message(db=db, message=message)
    return {"message": f"Message deleted with id {id_value}"}


async def delete_all_messages(db: AsyncSession):
    await message_repository.delete_all_messages(db=db)
    return {"message": "All messages deleted successfully"}