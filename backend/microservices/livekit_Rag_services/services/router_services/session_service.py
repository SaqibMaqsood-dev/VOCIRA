from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio

from backend.microservices.livekit_Rag_services.repository.session_repository import SessionRepository
from backend.microservices.livekit_Rag_services.core.rabitmq import RabbitMQ
from backend.microservices.livekit_Rag_services.models import (
    escalation_model,
    message_model,
    session_model,
)
from backend.helper_functions.database.session import SessionLocal
from backend.microservices.livekit_Rag_services.core.config import settings


class SessionService:

    def __init__(self):
        self.session_repo = SessionRepository()

    # =========================================================
    # CREATE SESSION (transaction-safe)
    # =========================================================
    async def create_session(self, db: AsyncSession, user_id: UUID | None):
        try:
            async with db.begin():  # transaction block
                new_session = await self.session_repo.session_create(
                    db=db,
                    user_id=user_id,
                )

                if not new_session:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create session",
                    )

                session_id = new_session.id
                print(f"🆕 [SessionService] Session created: {session_id} | user_id={user_id}")

                # flush + refresh inside transaction
                await db.flush()
                await db.refresh(new_session)

            # after transaction exits, commit is guaranteed
            # ✅ retry mechanism to handle commit visibility
            retries = 3
            saved_session = None
            for attempt in range(retries):
                result = await db.execute(
                    select(session_model.Session).where(session_model.Session.id == session_id)
                )
                saved_session = result.scalar_one_or_none()
                if saved_session:
                    if attempt > 0:
                        print(f"✅ [SessionService] Session found after retry {attempt}")
                    break
                else:
                    if attempt < retries - 1:
                        print(f"⚠️ [SessionService] Session not visible yet | Retrying...")
                        await asyncio.sleep(0.2)
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Session was committed but could not be found.",
                        )

            print(f"✅ [SessionService] Session verified successfully: {session_id}")

            # publish only once, after verification
            await RabbitMQ().producer(message={"session_id": str(session_id)})
            print(f"📤 [SessionService] Session published to RabbitMQ: {session_id}")

            return saved_session

        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            print(f"❌ [SessionService] Failed to create session: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session",
            )

    # =========================================================
    # GET USER SESSIONS
    # =========================================================
    async def get_user_sessions(self, db: AsyncSession, user_id: UUID, limit: int = 10, skip: int = 0):
        rows = await self.session_repo.get_user_sessions(
            db=db, user_id=user_id, limit=limit, skip=skip
        )
        return await self._decorate(db=db, sessions=rows)

    # =========================================================
    # DURATION AUR HANDLER
    # =========================================================

    async def _decorate(self, db: AsyncSession, sessions: list):
        """
        Har session par duration aur handler chipka dein.

        Dashboard ki ye do columns hamesha "-" dikhati thin kyunke API
        ye maloomat deti hi nahi thi.

        Escalations ek hi query mein nikaali jati hain, har session ke
        liye alag nahi - warna 20 rows ka matlab 20 queries hota.
        """

        if not sessions:
            return sessions

        ids = [s.id for s in sessions]

        # Kis kis session mein insaan tak baat gayi.
        # Escalation message se juRi hai, message session se.
        escalated = set(
            (
                await db.execute(
                    select(message_model.Message.session_id)
                    .join(
                        escalation_model.Escalation,
                        escalation_model.Escalation.message_id
                        == message_model.Message.id,
                    )
                    .where(message_model.Message.session_id.in_(ids))
                    .distinct()
                )
            )
            .scalars()
            .all()
        )

        for row in sessions:
            row.handler = "Human" if row.id in escalated else "AI"

            # Chalti hui call ki koi duration nahi hoti - wo abhi barh
            # rahi hai. Us par koi ginti dikhana jhoot hoga.
            if row.end_at and row.start_at:
                row.duration_seconds = max(
                    0, int((row.end_at - row.start_at).total_seconds())
                )
            else:
                row.duration_seconds = None

        return sessions

    # =========================================================
    # GET ALL SESSIONS
    # =========================================================
    async def get_all_sessions(self, db: AsyncSession, limit: int = 10, skip: int = 0):
        return await self.session_repo.get_all_sessions(db=db, limit=limit, skip=skip)

    # =========================================================
    # GET USER SESSION BY ID
    # =========================================================
    async def get_session_by_id(self, db: AsyncSession, user_id: UUID, id_value: UUID):
        session = await self.session_repo.get_by_id(db=db, id=id_value)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if session.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this session")
        return session

    # =========================================================
    # DASHBOARD STATS
    # =========================================================
    async def get_dashboard_stats(self, db: AsyncSession, user_id: UUID):
        return {
            "total_calls": await self.session_repo.count_user_sessions(db=db, user_id=user_id),
            "today_calls": await self.session_repo.count_today_sessions(db=db, user_id=user_id),
            "this_week_calls": await self.session_repo.count_week_sessions(db=db, user_id=user_id),
        }

    # =========================================================
    # CLOSE USER SESSION
    # =========================================================
    # Do tarah ke caller hain:
    #   router            -> apna injected db bhejta hai
    #   livekit worker    -> uske paas koi db session nahi hoti
    # Is liye db optional hai; na mile to yahin ek khol lete hain.
    async def close_session_by_id(
        self,
        user_id: UUID,
        session_id: UUID,
        db: AsyncSession | None = None,
    ):
        if db is not None:
            return await self._close(db=db, user_id=user_id, session_id=session_id)

        async with SessionLocal() as own_db:
            return await self._close(db=own_db, user_id=user_id, session_id=session_id)

    async def _close(self, db: AsyncSession, user_id: UUID, session_id: UUID):
        async with db.begin():  # transaction block for closing
            session = await self.session_repo.get_by_id(db=db, id=session_id)
            if not session:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
            if session.user_id != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this session")
            return await self.session_repo.close_session_by_id(db=db, session_id=session_id)
