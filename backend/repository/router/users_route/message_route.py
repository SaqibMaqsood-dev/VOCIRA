from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from database import database
from models import message_model
from schema import message_schema
from sqlalchemy import delete
from services.rbac.required_permission import require_permission
from tokken.access_tokken.get_current_user import current_user
from models.session_model import Session , SessionStatus

router = APIRouter(prefix="/messages", tags=["Messages"])





@router.get("/get_message", response_model=List[message_schema.MessageResponse])
async def get_messages(db: AsyncSession = Depends(database.get_db)):
    try:
        result = await db.execute(select(message_model.Message))
        messages = result.scalars().all()

        if not messages:
            raise HTTPException(status_code=404, detail="No messages found")
        
        return messages
    

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@router.get("/{id}", response_model=message_schema.MessageResponse)
async def get_message_by_id(id: int, db: AsyncSession = Depends(database.get_db)):
    try:
        result = await db.execute(
            select(message_model.Message).where(message_model.Message.id == id)
        )
        message = result.scalar_one_or_none()

        if not message:
            raise HTTPException(
                status_code=404,
                detail=f"No message found with id {id}"
            )
        return message

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/session/{session_id}", response_model=List[message_schema.MessageResponse])
async def get_messages_by_session(
    session_id: int,
    db: AsyncSession = Depends(database.get_db)):

    try:
        result = await db.execute(
            select(message_model.Message).where( message_model.Message.session_id == session_id )
        )

        messages = result.scalars().all()

        if not messages:
            raise HTTPException(
                status_code=404,
                detail=f"No messages found for session {session_id}"
            )

        return messages

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    



@router.delete("/{id}")
async def delete_message(id: int, db: AsyncSession = Depends(database.get_db)):
    try:
        result = await db.execute(
            select(message_model.Message).where(message_model.Message.id == id)
        )

        message = result.scalar_one_or_none()

        if not message:
            raise HTTPException(
                status_code=404,
                detail=f"No message found with id {id}"
            )

        await db.delete(message)
        await db.commit()

        return {"message": f"Message deleted with id {id}"}

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.put("/{id}")
async def update_message(
    request: message_schema.MessageCreate,
    id: int,
    db: AsyncSession = Depends(database.get_db)
):
    try:
        result = await db.execute(
            select(message_model.Message).where(message_model.Message.id == id)
        )

        message = result.scalar_one_or_none()

        if not message:
            raise HTTPException(
                status_code=404,
                detail=f"No message found with id {id}"
            )

        message  = message_model.Message(
            session_id  = 1,
            user_id     = 1,
            sender_type = request.sender_type,
            intent      = "text",
            source_type = request.source_type,
            content     = request.content
        )


        await db.commit()
        await db.refresh(message)

        return {"message": "Message updated successfully"}

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.patch("/{id}")
async def partial_update_message(
    request: message_schema.MessagePartialUpdate,
    id: int,
    db: AsyncSession = Depends(database.get_db)
):
    try:
        result = await db.execute(
            select(message_model.Message).where(message_model.Message.id == id)
        )
        message = result.scalar_one_or_none()
        if not message:
            raise HTTPException(
                status_code=404,
                detail=f"No message found with id {id}"
            )
        data = request.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(message, key, value)

        await db.commit()
        await db.refresh(message)

        return {
            "message": "Message partially updated",
            "updated_fields": data
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/messages/delete_all")
async def delete_all_messages(db: AsyncSession = Depends(database.get_db)):
    try:
        await db.execute(delete(message_model.Message))
        await db.commit()
        return {"message": "All messages deleted successfully"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))