from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import asyncio

from datetime import datetime, timezone

from backend.microservices.livekit_Rag_services.repository.session_repository import (
    SessionRepository,
)

from backend.microservices.livekit_Rag_services.core.rabitmq import (
    RabbitMQ,
)

from backend.microservices.livekit_Rag_services.models import (
    session_model,
)

from backend.helper_functions.database.session import (
    SessionLocal,
)


class SessionService:

    def __init__(self):

        self.session_repo = SessionRepository()

    # =========================================================
    # CREATE SESSION
    # =========================================================

    async def create_session(
        self,
        db: AsyncSession,
        user_id: UUID | None,
    ):

        try:

            # =====================================================
            # CREATE DATABASE SESSION
            # =====================================================

            async with db.begin():

                new_session = (
                    await self.session_repo.session_create(
                        db=db,
                        user_id=user_id,
                    )
                )

                if not new_session:

                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create session",
                    )

                session_id = new_session.id

                print("=" * 70)

                print(
                    "🆕 [SessionService] Session created"
                )

                print(
                    f"Session ID : {session_id}"
                )

                print(
                    f"User ID    : {user_id}"
                )

                print("=" * 70)

                await db.flush()

                await db.refresh(
                    new_session
                )

            # =====================================================
            # VERIFY COMMITTED SESSION
            # =====================================================

            retries = 3
            saved_session = None

            for attempt in range(retries):

                result = await db.execute(
                    select(
                        session_model.Session
                    ).where(
                        session_model.Session.id
                        == session_id
                    )
                )

                saved_session = (
                    result.scalar_one_or_none()
                )

                if saved_session:

                    if attempt > 0:

                        print(
                            f"✅ [SessionService] "
                            f"Session found after retry "
                            f"{attempt}"
                        )

                    break

                if attempt < retries - 1:

                    print(
                        "⚠️ [SessionService] "
                        "Session not visible yet. "
                        "Retrying..."
                    )

                    await asyncio.sleep(
                        0.2
                    )

                else:

                    raise HTTPException(
                        status_code=(
                            status.HTTP_500_INTERNAL_SERVER_ERROR
                        ),
                        detail=(
                            "Session was committed "
                            "but could not be found."
                        ),
                    )

            print(
                f"✅ [SessionService] "
                f"Session verified successfully: "
                f"{session_id}"
            )

            # =====================================================
            # PUBLISH SESSION TO RABBITMQ
            #
            # IMPORTANT:
            #
            # user_id MUST be included here.
            #
            # The background LiveKit worker receives this
            # user_id and keeps it for session closing.
            #
            # Guest:
            #     user_id = None
            #
            # Authenticated:
            #     user_id = actual UUID
            # =====================================================

            rabbit_message = {
                "session_id": str(
                    session_id
                ),
                "user_id": (
                    str(user_id)
                    if user_id is not None
                    else None
                ),
            }

            print("=" * 70)

            print(
                "📤 [SessionService] "
                "Publishing session.created event"
            )

            print(
                f"Session ID : "
                f"{rabbit_message['session_id']}"
            )

            print(
                f"User ID    : "
                f"{rabbit_message['user_id']}"
            )

            print("=" * 70)

            await RabbitMQ().producer(
                message=rabbit_message
            )

            print(
                f"✅ [SessionService] "
                f"Session published to RabbitMQ: "
                f"{session_id}"
            )

            return saved_session

        except HTTPException:

            await db.rollback()

            raise

        except Exception as e:

            await db.rollback()

            print(
                f"❌ [SessionService] "
                f"Failed to create session: {e}"
            )

            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail="Failed to create session",
            )

    # =========================================================
    # GET USER SESSIONS
    # =========================================================

    async def get_user_sessions(
        self,
        db: AsyncSession,
        user_id: UUID,
        limit: int = 10,
        skip: int = 0,
    ):

        return await self.session_repo.get_user_sessions(
            db=db,
            user_id=user_id,
            limit=limit,
            skip=skip,
        )

    # =========================================================
    # GET ALL SESSIONS
    # =========================================================

    async def get_all_sessions(
        self,
        db: AsyncSession,
        limit: int = 10,
        skip: int = 0,
    ):

        return await self.session_repo.get_all_sessions(
            db=db,
            limit=limit,
            skip=skip,
        )

    # =========================================================
    # GET USER SESSION BY ID
    # =========================================================

    async def get_session_by_id(
        self,
        db: AsyncSession,
        user_id: UUID,
        id_value: UUID,
    ):

        session = await self.session_repo.get_by_id(
            db=db,
            id=id_value,
        )

        if not session:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        # =====================================================
        # USER OWNERSHIP CHECK
        #
        # This remains for normal user-facing access.
        # =====================================================

        if session.user_id != user_id:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You do not have access "
                    "to this session"
                ),
            )

        return session

    # =========================================================
    # DASHBOARD STATS
    # =========================================================

    async def get_dashboard_stats(
        self,
        db: AsyncSession,
        user_id: UUID,
    ):

        return {

            "total_calls":
                await self.session_repo.count_user_sessions(
                    db=db,
                    user_id=user_id,
                ),

            "today_calls":
                await self.session_repo.count_today_sessions(
                    db=db,
                    user_id=user_id,
                ),

            "this_week_calls":
                await self.session_repo.count_week_sessions(
                    db=db,
                    user_id=user_id,
                ),
        }

    async def close_session_by_id(
        self,
        session_id: UUID,
        user_id: UUID | None = None,
    ):

        async with SessionLocal() as db:

            try:

                # =================================================
                # GET SESSION
                # =================================================

                async with db.begin():

                    session = (
                        await self.session_repo.get_by_id(
                            db=db,
                            id=session_id,
                        )
                    )

                    if not session:

                        raise HTTPException(
                            status_code=(
                                status.HTTP_404_NOT_FOUND
                            ),
                            detail="Session not found",
                        )

                    print("=" * 70)

                    print(
                        "🔎 [SessionService] "
                        "Closing session"
                    )

                    print(
                        f"Session ID       : "
                        f"{session.id}"
                    )

                    print(
                        f"Database User ID : "
                        f"{session.user_id}"
                    )

                    print(
                        f"Provided User ID : "
                        f"{user_id}"
                    )

                    print(
                        f"Current Status   : "
                        f"{session.status}"
                    )

                    print("=" * 70)

                    # =================================================
                    # ALREADY CLOSED
                    # =================================================

                    if (
                        session.status
                        == session_model.SessionStatus.closed
                    ):

                        print(
                            f"ℹ️ [SessionService] "
                            f"Session already closed: "
                            f"{session_id}"
                        )

                        return session

                    # =================================================
                    # AUTHENTICATED SESSION
                    # =================================================

                    if session.user_id is not None:

                        # -------------------------------------------------
                        # Worker did not receive user_id
                        # -------------------------------------------------

                        if user_id is None:

                            raise HTTPException(
                                status_code=(
                                    status.HTTP_403_FORBIDDEN
                                ),
                                detail=(
                                    "Authenticated session "
                                    "requires a user ID"
                                ),
                            )

                        # -------------------------------------------------
                        # Verify ownership
                        # -------------------------------------------------

                        if session.user_id != user_id:

                            raise HTTPException(
                                status_code=(
                                    status.HTTP_403_FORBIDDEN
                                ),
                                detail=(
                                    "You do not have access "
                                    "to this session"
                                ),
                            )

                        print(
                            "✅ [SessionService] "
                            "Authenticated session "
                            "ownership verified."
                        )

                    # =================================================
                    # GUEST SESSION
                    # =================================================

                    else:

                        if user_id is not None:

                            raise HTTPException(
                                status_code=(
                                    status.HTTP_403_FORBIDDEN
                                ),
                                detail=(
                                    "Authenticated user "
                                    "cannot close a guest "
                                    "session"
                                ),
                            )

                        print(
                            "👤 [SessionService] "
                            "Guest session detected."
                        )

                    # =================================================
                    # CLOSE SESSION
                    #
                    # Database uses:
                    #
                    #     TIMESTAMP WITHOUT TIME ZONE
                    #
                    # Therefore we store UTC as a naive datetime.
                    # =================================================

                    session.end_at = (
                        datetime.now(timezone.utc)
                        .replace(tzinfo=None)
                    )

                    session.status = (
                        session_model.SessionStatus.closed
                    )

                    # =================================================
                    # FLUSH
                    # =================================================

                    await db.flush()

                    await db.refresh(
                        session
                    )

                    # =================================================
                    # CALCULATE DURATION
                    # =================================================

                    duration = None

                    if (
                        session.start_at
                        and session.end_at
                    ):

                        start_at = session.start_at

                        end_at = session.end_at

                        # -------------------------------------------------
                        # Safety normalization
                        #
                        # SQLAlchemy/PostgreSQL may return naive
                        # datetimes because the column is
                        # TIMESTAMP WITHOUT TIME ZONE.
                        #
                        # If either value somehow contains timezone
                        # information, normalize it to naive UTC.
                        # -------------------------------------------------

                        if start_at.tzinfo is not None:

                            start_at = (
                                start_at.astimezone(
                                    timezone.utc
                                ).replace(
                                    tzinfo=None
                                )
                            )

                        if end_at.tzinfo is not None:

                            end_at = (
                                end_at.astimezone(
                                    timezone.utc
                                ).replace(
                                    tzinfo=None
                                )
                            )

                        duration = (
                            end_at - start_at
                        ).total_seconds()

                    # =================================================
                    # LOG
                    # =================================================

                    print("=" * 70)

                    print(
                        "🔴 [SESSION CLOSED]"
                    )

                    print(
                        f"Session ID : "
                        f"{session.id}"
                    )

                    print(
                        f"User ID    : "
                        f"{session.user_id}"
                    )

                    print(
                        f"Start At   : "
                        f"{session.start_at}"
                    )

                    print(
                        f"End At     : "
                        f"{session.end_at}"
                    )

                    print(
                        f"Status     : "
                        f"{session.status}"
                    )

                    print(
                        f"Handler    : "
                        f"{session.handler}"
                    )

                    print(
                        f"Duration   : "
                        f"{duration} seconds"
                    )

                    print("=" * 70)

                    return session

            except HTTPException:

                raise

            except Exception as error:

                await db.rollback()

                print("=" * 70)

                print(
                    "❌ [SessionService] "
                    "Failed to close session:"
                )

                print(
                    f"Session ID : {session_id}"
                )

                print(
                    f"User ID    : {user_id}"
                )

                print(
                    f"Error      : {error}"
                )

                print("=" * 70)

                raise
