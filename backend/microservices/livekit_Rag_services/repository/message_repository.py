from sqlalchemy import select, delete as sqlalchemy_delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.microservices.livekit_Rag_services.models.message_model import (
    Message
)
from backend.helper_functions.base_repository.base_repository import BaseRepository

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.microservices.livekit_Rag_services.models.message_model import (
    Message,
    SenderTypeEnum,
    SourceTypeEnum,
)


class MessageRepository(BaseRepository[Message]):
    def __init__(self, model_cls):
        super().__init__(model_cls=Message)

    async def create(
        self,
        db: AsyncSession,
        content: str,
        session_id: UUID,
        user_id: UUID | None = None,
        sender_type: SenderTypeEnum = SenderTypeEnum.guest,
        intent: str | None = None,
        source_type: SourceTypeEnum = SourceTypeEnum.database,
    ):
        try:
            
            new_message = Message(
                session_id=session_id,
                user_id=user_id,
                sender_type=sender_type,
                content=content,
                intent=intent,
                source_type=source_type,
            )

            db.add(new_message)

            await db.commit()
            await db.refresh(new_message)

            return new_message

        except Exception:
            await db.rollback()
            raise