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
        Create a new voice session.

        Authenticated user:
            user_id = actual VOCIRA user UUID

        Guest:
            user_id = None

        New sessions always start as:

            status  = active
            handler = ai
        """

        new_session = session_model.Session(
            user_id=user_id,
            title="Voice Agent Session",

            # -------------------------------------------------
            # Session starts ACTIVE
            # -------------------------------------------------
            status=session_model.SessionStatus.active,

            # -------------------------------------------------
            # Initial handler is AI
            # -------------------------------------------------
            handler=session_model.SessionHandler.ai,

            # -------------------------------------------------
            # Start time
            #
            # Database uses TIMESTAMP WITHOUT TIME ZONE,
            # therefore store naive UTC.
            # -------------------------------------------------
            start_at=datetime.now(timezone.utc).replace(
                tzinfo=None
            ),

            # Session is not closed yet.
            end_at=None,
        )

        db.add(new_session)

        # Make sure ID/default values are generated.
        await db.flush()
        await db.refresh(new_session)

        print(
            f"🆕 [SessionRepository] "
            f"Session created: {new_session.id} | "
            f"user_id={user_id} | "
            f"status={new_session.status} | "
            f"handler={new_session.handler} | "
            f"start_at={new_session.start_at}"
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
        """
        Return only sessions belonging to the authenticated user.
        """

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
            f"Found {len(sessions)} sessions "
            f"for user_id={user_id}"
        )

        for session in sessions:
            print(
                f"   → "
                f"session_id={session.id}, "
                f"user_id={session.user_id}, "
                f"status={session.status}, "
                f"handler={session.handler}, "
                f"start_at={session.start_at}, "
                f"end_at={session.end_at}"
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
        This should only be exposed to admin/internal services.
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
    # GET SESSION BY ID
    # =========================================================

    async def get_by_id(
        self,
        db: AsyncSession,
        id: UUID,
    ):
        """
        Get a single session by ID.
        """

        stmt = (
            select(session_model.Session)
            .where(
                session_model.Session.id == id
            )
        )

        result = await db.execute(stmt)

        return result.scalar_one_or_none()

    # =========================================================
    # COUNT USER SESSIONS
    # =========================================================

    async def count_user_sessions(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> int:
        """
        Count all sessions belonging to this user.
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
        Count user's sessions created today.

        Database:
            TIMESTAMP WITHOUT TIME ZONE
        """

        now = datetime.now(timezone.utc)

        start_of_day = datetime(
            now.year,
            now.month,
            now.day,
        )

        end_of_day = (
            start_of_day + timedelta(days=1)
        )

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
        Count user's sessions from Monday until next Monday.
        """

        now = datetime.now(timezone.utc)

        start_of_today = datetime(
            now.year,
            now.month,
            now.day,
        )

        start_of_week = (
            start_of_today
            - timedelta(days=now.weekday())
        )

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
        Close an existing session.

        This method:

            active
              ↓
            closed

        and sets:

            end_at = current UTC time

        Duration is then automatically calculated by
        SessionResponse using:

            end_at - start_at

        IMPORTANT:
        This repository method does NOT call db.commit().
        The service layer owns the transaction.
        """

        stmt = (
            select(session_model.Session)
            .where(
                session_model.Session.id == session_id
            )
        )

        result = await db.execute(stmt)

        session = result.scalar_one_or_none()

        # -----------------------------------------------------
        # SESSION NOT FOUND
        # -----------------------------------------------------

        if not session:
            print(
                f"⚠️ [SessionRepository] "
                f"No session found: {session_id}"
            )

            return None

        # -----------------------------------------------------
        # ALREADY CLOSED
        # -----------------------------------------------------

        if (
            session.status
            == session_model.SessionStatus.closed
        ):
            print(
                f"ℹ️ [SessionRepository] "
                f"Session already closed: {session_id}"
            )

            # Make sure any existing data is loaded.
            await db.refresh(session)

            return session

        # -----------------------------------------------------
        # ONLY ACTIVE SESSIONS CAN BE CLOSED
        # -----------------------------------------------------

        if (
            session.status
            != session_model.SessionStatus.active
        ):
            print(
                f"⚠️ [SessionRepository] "
                f"Unexpected session status: "
                f"{session.status}"
            )

            return session

        # -----------------------------------------------------
        # UPDATE STATUS
        # -----------------------------------------------------

        session.status = (
            session_model.SessionStatus.closed
        )

        # -----------------------------------------------------
        # SET END TIME
        # -----------------------------------------------------

        session.end_at = (
            datetime.now(timezone.utc)
            .replace(tzinfo=None)
        )

        # -----------------------------------------------------
        # DURATION
        #
        # We do not store duration in DB.
        #
        # SessionResponse calculates:
        #
        # end_at - start_at
        # -----------------------------------------------------

        print(
            f"🔒 [SessionRepository] "
            f"Closing session: {session_id}"
        )

        print(
            f"   → start_at={session.start_at}"
        )

        print(
            f"   → end_at={session.end_at}"
        )

        # -----------------------------------------------------
        # FLUSH CHANGES
        #
        # Do NOT commit here.
        # SessionService controls transaction.
        # -----------------------------------------------------

        await db.flush()
        await db.refresh(session)

        # -----------------------------------------------------
        # LOG CALCULATED DURATION
        # -----------------------------------------------------

        if (
            session.start_at
            and session.end_at
        ):
            duration_seconds = int(
                (
                    session.end_at
                    - session.start_at
                ).total_seconds()
            )

            duration_seconds = max(
                0,
                duration_seconds,
            )

            print(
                f"⏱️ [SessionRepository] "
                f"Duration: "
                f"{duration_seconds} seconds"
            )

        print(
            f"✅ [SessionRepository] "
            f"Session closed successfully: "
            f"{session_id} | "
            f"status={session.status} | "
            f"handler={session.handler}"
        )

        return session