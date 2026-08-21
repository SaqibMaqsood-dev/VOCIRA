from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.microservices.livekit_Rag_services.repository.session_repository import (
SessionRepository,)
from backend.microservices.livekit_Rag_services.models.session_model import (
Session
)
from backend.microservices.livekit_Rag_services.core.rabitmq import RabbitMQ
from backend.helper_functions.database import SessionLocal
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.microservices.livekit_Rag_services.core.rabitmq import RabbitMQ
from backend.microservices.livekit_Rag_services.models import session_model 
from backend.helper_functions.database import SessionLocal

from uuid import UUID
    

class SessionService:

    def __init__(self):
        self.session_repo = SessionRepository()

    # =========================================================
    # CREATE SESSION
    # =========================================================

    async def create_session(
        self,
        user_id,
    ) -> dict:
        """
        Creates a new session and publishes the session ID
        to RabbitMQ.

        Used internally by LiveKit token/session creation.
        """
            
        new_session = await self.session_repo.session_create(
            user_id = user_id
        )

        if not new_session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session",
            )
        
        await RabbitMQ().producer(
            message={
                "session_id":str(new_session.id),
            }
        )

        return new_session

    # =========================================================
    # GET ALL SESSIONS
    # =========================================================

    async def get_all_sessions(
        self,
        db: AsyncSession,
    ):
        sessions = await self.session_repo.get_multi(
            db=db,
        )

        if not sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No sessions found",
            )

        return sessions

    
    # =========================================================
    # GET SESSION BY ID
    # =========================================================


    async def get_session_by_id(
        self,
        db: AsyncSession,
        id_value: UUID,
    ):
        session = await self.session_repo.get_by_id(
            db=db,
            id=id_value,
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No session found with id {id_value}",
            )

        return session

    # =========================================================
    # UPDATE SESSION
    # =========================================================
    
    async def update_session(
        self,
        db: AsyncSession,
        id_value: UUID,
        request,
    ):
        session = await self.session_repo.get_by_id(
            db=db,
            id_value=id_value,
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No session found with id {id_value}",
            )

        data = {
            "title": request.title,
        }

        updated_session = await self.session_repo.update(
            db=db,
            session=session,
            data=data,
        )

        return updated_session

    # =========================================================
    # PARTIAL UPDATE SESSION
    # =========================================================

    async def partial_update_session(
        self,
        db: AsyncSession,
        id_value: UUID,
        request,
    ):
        session = await self.session_repo.get_by_id(
            db=db,
            id_value=id_value,
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No session found with id {id_value}",
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

        updated_session = await self.session_repo.update(
            db=db,
            session=session,
            data=data,
        )

        return updated_session

    # =========================================================
    # DELETE SESSION
    # =========================================================

    async def delete_session(
        self,
        db: AsyncSession,
        id_value: UUID,
    ):
        session = await self.session_repo.get_by_id(
            db=db,
            id_value=id_value,
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No session found with id {id_value}",
            )

        await self.session_repo.delete(
            db=db,
            session=session,
        )

        return {
            "message": f"Session deleted with id {id_value}",
        }

    # =========================================================
    # CLOSE SESSION
    # =========================================================

    async def close_session_by_id(
        self,
        session_id,
    ) -> None:
        """
        Used internally by the LiveKit worker when
        a session is finished.
        """

        try:
            clean_session_id = UUID(session_id)

        except (ValueError, TypeError):

            print(
                f"❌ [Session Cleanup] "
                f"Invalid session_id format: {session_id}"
            )

            return

        async with SessionLocal() as db:

            try:

                session = await self.session_repo.get_by_id(
                    db=db,
                    id=clean_session_id,
                )

                if not session:

                    print(
                        f"⚠️ [Session Cleanup] "
                        f"No session found for ID: {clean_session_id}"
                    )

                    return

                if session.status == session_model.SessionStatus.closed:

                    print(
                        f"ℹ️ [Session Cleanup] "
                        f"Session {clean_session_id} already closed."
                    )

                    return

                await self.session_repo.close_session_by_id(
                    db=db,
                    session=session,
                )

                print(
                    f"🔒 [Session Cleanup] "
                    f"Session {clean_session_id} closed."
                )

            except Exception as e:

                await db.rollback()

                print(
                    f"❌ [Session Cleanup Error] "
                    f"Transaction failed: {e}"
                )
