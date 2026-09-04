from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.microservices.livekit_Rag_services.repository.message_repository import (
    MessageRepository,
)

from backend.microservices.auth_services.models import user_model 
from backend.microservices.livekit_Rag_services.models import message_model
from backend.microservices.livekit_Rag_services.models.session_model import Session , SessionStatus
from backend.microservices.livekit_Rag_services.models.message_model import SenderTypeEnum , SourceTypeEnum
from sqlalchemy.orm import selectinload
from uuid import UUID


# Call sites `usertype` mein kabhi enum ki value bhejte hain
# ("guardian", "ai") aur kabhi us ka naam ("user"). Pehle yahan
# sirf "guest"/"agent"/"admin" ke literals check hote the, is liye
# `SenderTypeEnum.ai.value` == "ai" kisi shart par pura nahi utarta
# tha aur har AI jawab `else` branch se guzar kar `user` ban jata
# tha - database mein agent ki apni baat guardian ke naam likhi
# ja rahi thi. Ab dono shaklein yahan se guzarti hain.
_SENDER_ALIASES = {
    SenderTypeEnum.ai.value: SenderTypeEnum.ai,           # "ai"
    "agent": SenderTypeEnum.ai,                           # purana naam
    SenderTypeEnum.admin.value: SenderTypeEnum.admin,     # "admin"
    SenderTypeEnum.guest.value: SenderTypeEnum.guest,     # "guest"
    SenderTypeEnum.user.value: SenderTypeEnum.user,       # "guardian"
    "user": SenderTypeEnum.user,
}


class MessageService:

    def __init__(self):
        self.message_repo = MessageRepository(model_cls=message_model.Message)

    async def create_message(
        self,
        db: AsyncSession,
        content: str,
        user_id=None,
        usertype: str = "guest",
        session_id=None,
        intent: str | None = "voice_input",
        source_type: SourceTypeEnum = SourceTypeEnum.database,
    ):

        # -----------------------------
        # Determine sender
        # -----------------------------

        sender_type = _SENDER_ALIASES.get(
            (usertype or "").strip().lower(),
            SenderTypeEnum.guest,
        )

        if sender_type is SenderTypeEnum.ai:

            # Agent ka apna jawab kisi user se mansoob nahi hota
            user_id = None

        elif sender_type is SenderTypeEnum.guest:

            user_id = None

        elif sender_type is SenderTypeEnum.user and not user_id:

            # Bina login ke aane wali baat guardian nahi hoti
            sender_type = SenderTypeEnum.guest

        # -----------------------------
        # Create message
        # -----------------------------
        
        created_message = await self.message_repo.create(
            db=db,
            content=content,
            session_id=session_id,
            user_id=user_id,
            sender_type=sender_type,
            intent=intent,
            source_type=source_type,
        )

        return created_message
               

    # =========================================================
    # GET ALL  
    # =========================================================


    async def get_all_messages(
        self,
        db: AsyncSession,
        limit: int = 10,
        skip: int = 0,
    ):
        messages = await self.message_repo.get_multi(
            db=db,
            limit=limit,
            skip=skip,
        )

        if not messages:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No messages found",
            )

        return messages

    # =========================================================
    # GET BY ID
    # =========================================================

    async def get_message_by_id(
        self,
        db: AsyncSession,
        id_value: UUID,
    ):
        message = await self.message_repo.get_by_id(
            db=db,
            id_value=id_value,
        )
    
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No message found with id {id_value}",
            )

        return message


    # =========================================================
    # UPDATE
    # =========================================================

    async def update_message(
        self,
        db: AsyncSession,
        id_value: UUID,
        request,
    ):
        message = await self.message_repo.get_by_id(
            db=db,
            id_value=id_value,
        )

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No message found with id {id_value}",
            )

        data = {
            "sender_type": request.sender_type,
            "intent": "text",
            "source_type": request.source_type,
            "content": request.content,
        }

        updated_message = await self.message_repo.update(
            db=db,
            message=message,
            data=data,
        )

        return updated_message

    # =========================================================
    # PARTIAL UPDATE
    # =========================================================

    async def partial_update_message(
        self,
        db: AsyncSession,
        id_value: UUID,
        request,
    ):
        message = await self.message_repo.get_by_id(
            db=db,
            id_value=id_value,
        )

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No message found with id {id_value}",
            )

        data = request.model_dump(
            exclude_unset=True,
            exclude_none=True,
        )

        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update",
            )

        updated_message = await self.message_repo.update(
            db=db,
            message=message,
            data=data,
        )

        return updated_message

    # =========================================================
    # DELETE
    # =========================================================

    async def delete_message(
        self,
        db: AsyncSession,
        id_value: UUID,
    ):
        message = await self.message_repo.get_by_id(
            db=db,
            id_value=id_value,
        )

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No message found with id {id_value}",
            )

        await self.message_repo.delete(
            db=db,
            message=message,
        )

        return {
            "message": f"Message deleted with id {id_value}"
        }

    # =========================================================
    # DELETE ALL
    # =========================================================

    async def delete_all_messages(
        self,
        db: AsyncSession,
    ):
        await self.message_repo.delete_all(
            db=db,
        )

        return {
            "message": "All messages deleted successfully"
        }



    # =========================================================
    # GET BY SESSION
    # =========================================================

    async def get_messages_by_session(
        self,
        db: AsyncSession,
        session_id: UUID,
    ):
        messages = await self.message_repo.get_messages_by_session(
            db=db,
            session_id=session_id,
        )

        if not messages:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No messages found for session {session_id}",
            )

        return messages