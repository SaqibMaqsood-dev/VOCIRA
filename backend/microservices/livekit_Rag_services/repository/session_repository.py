from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.helper_functions.base_repository.base_repository import (
    BaseRepository,
)

from backend.microservices.livekit_Rag_services.models import (
    session_model,
)


class SessionRepository(
    BaseRepository[session_model.Session]
):

    def __init__(self):
        super().__init__(session_model.Session)

    # =========================================================
    # CREATE SESSION
    # =========================================================

    async def session_create(
        self,
        db: AsyncSession,
        user_id: UUID | None,
    ):
        """
        Create a voice session.

        Authenticated parent:
            user_id = actual UUID

        Guest:
            user_id = None
        """

        new_session = session_model.Session(
            user_id=user_id,
            title="Voice Agent Session",
            status=session_model.SessionStatus.active,
        )

        db.add(new_session)

        await db.flush()
        await db.refresh(new_session)

        print(
            f"🆕 [SessionRepository] "
            f"Session created: {new_session.id} | "
            f"user_id={user_id}"
        )

        return new_session

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
        print(
            f"🔎 [SessionRepository] "
            f"Fetching sessions for user_id={user_id}"
        )

        stmt = (
            select(session_model.Session)
            .where(
                session_model.Session.user_id == user_id
            )
            .order_by(
                session_model.Session.start_at.desc()
            )
            .offset(skip)
            .limit(limit)
        )

        result = await db.execute(stmt)

        sessions = result.scalars().all()

        print(
            f"📦 [SessionRepository] "
            f"Found {len(sessions)} sessions for user_id={user_id}"
        )

        for session in sessions:
            print(
                f"   → session_id={session.id}, "
                f"session_user_id={session.user_id}"
            )

        return sessions

    # =========================================================
    # GET ALL SESSIONS
    # =========================================================

    async def get_all_sessions(
        self,
        db: AsyncSession,
        limit: int = 10,
        skip: int = 0,
    ):
        """
        Return all sessions.

        IMPORTANT:
        This method must ONLY be exposed to admins/internal
        services.

        A normal parent must NEVER call this endpoint.
        """

        stmt = (
            select(session_model.Session)
            .order_by(
                session_model.Session.start_at.desc()
            )
            .offset(skip)
            .limit(limit)
        )

        result = await db.execute(stmt)

        return result.scalars().all()

    # =========================================================
    # COUNT USER SESSIONS
    # =========================================================

    async def count_user_sessions(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> int:
        """
        Count ONLY authenticated user's sessions.

        Guest sessions are excluded because:
            Session.user_id == user_id
        """

        stmt = (
            select(func.count())
            .select_from(session_model.Session)
            .where(
                session_model.Session.user_id == user_id
            )
        )

        result = await db.execute(stmt)

        return result.scalar_one()

    # =========================================================
    # COUNT TODAY'S USER SESSIONS
    # =========================================================

    async def count_today_sessions(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> int:
        """
        Count authenticated user's sessions created today.

        Database uses:
            TIMESTAMP WITHOUT TIME ZONE

        Therefore the datetime values sent to PostgreSQL
        must be timezone-naive.
        """

        # Get current UTC time
        now = datetime.now(timezone.utc)

        # Remove timezone information because the DB column
        # is TIMESTAMP WITHOUT TIME ZONE.
        start_of_day = datetime(
            now.year,
            now.month,
            now.day,
        )

        end_of_day = start_of_day + timedelta(days=1)

        stmt = (
            select(func.count())
            .select_from(session_model.Session)
            .where(
                session_model.Session.user_id == user_id,
                session_model.Session.start_at >= start_of_day,
                session_model.Session.start_at < end_of_day,
            )
        )

        result = await db.execute(stmt)

        return result.scalar_one()

    # =========================================================
    # COUNT THIS WEEK'S USER SESSIONS
    # =========================================================

    async def count_week_sessions(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> int:
        """
        Count authenticated user's sessions from Monday
        through the current week.

        Database uses:
            TIMESTAMP WITHOUT TIME ZONE

        Therefore all datetime values sent to PostgreSQL
        are timezone-naive.
        """

        # Get current UTC time
        now = datetime.now(timezone.utc)

        # Start of today as timezone-naive datetime
        start_of_today = datetime(
            now.year,
            now.month,
            now.day,
        )

        # Monday 00:00:00
        start_of_week = (
            start_of_today
            - timedelta(days=now.weekday())
        )

        # Next Monday 00:00:00
        end_of_week = (
            start_of_week
            + timedelta(days=7)
        )

        stmt = (
            select(func.count())
            .select_from(session_model.Session)
            .where(
                session_model.Session.user_id == user_id,
                session_model.Session.start_at >= start_of_week,
                session_model.Session.start_at < end_of_week,
            )
        )

        result = await db.execute(stmt)

        return result.scalar_one()

    # =========================================================
    # CLOSE SESSION
    # =========================================================

    async def close_session_by_id(
        self,
        db: AsyncSession,
        session_id: UUID,
    ):
        """
        Close a session by ID.

        Ownership should already be checked by SessionService
        before this method is called.
        """

        stmt = (
            select(session_model.Session)
            .where(
                session_model.Session.id == session_id
            )
        )

        result = await db.execute(stmt)

        session = result.scalar_one_or_none()

        if not session:

            print(
                f"⚠️ [Session Cleanup] "
                f"No session found: {session_id}"
            )

            return None

        # -----------------------------------------------------
        # Already closed
        # -----------------------------------------------------

        if (
            session.status
            == session_model.SessionStatus.closed
        ):

            print(
                f"ℹ️ [Session Cleanup] "
                f"Already closed: {session_id}"
            )

            return session

        # -----------------------------------------------------
        # Close session
        # -----------------------------------------------------

        session.status = (
            session_model.SessionStatus.closed
        )

        # Database column is TIMESTAMP WITHOUT TIME ZONE,
        # so store a timezone-naive UTC datetime.
        session.end_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        )

        await db.commit()

        await db.refresh(session)

        print(
            f"🔒 [Session Cleanup] "
            f"Session closed successfully: {session_id}"
        )

        return session