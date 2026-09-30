from datetime import datetime
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
from backend.microservices.livekit_Rag_services.models.message_model import SenderTypeEnum
from backend.helper_functions.database.session import SessionLocal
from backend.microservices.livekit_Rag_services.core.config import settings


# Resource keys, as stored in Message.intent, mapped to what a
# guardian should actually see. Falls back to a title-cased version
# of the raw key for anything not listed here.
_TOPIC_LABELS = {
    "attendance": "Attendance",
    "assessment": "Marks",
    "exam": "Upcoming exam",
    "schedule": "Timetable",
    "class": "Class",
    "course": "Subjects",
    "program_enrollment": "Enrollment",
    "fee": "Fees",
    "payment": "Payment",
    "student": "Profile",
    "guardian": "My details",
    "leave": "Leaves",
    "remarks": "Teacher remarks",
}


def _format_topic(raw: str) -> str:
    """
    Turn one stored `Message.intent` value into what shows up in the
    call table - "Zoya - Attendance" when a child was named,
    "Attendance" alone otherwise.

    A compound question ("Zoya's attendance and has the fee been
    paid?") stores more than one resource in a single message, joined
    with "+" (e.g. "attendance:Zoya+fee:Zoya") - each part is
    formatted the same way and joined with " & " for one combined
    topic instead of losing everything but the first part.
    """

    if not raw:
        return ""

    if raw == "admin_handoff":
        return "Escalated to staff"

    if raw in ("rag", "cached"):
        return "General question"

    if "+" in raw:
        return " & ".join(_format_topic(part) for part in raw.split("+") if part)

    resource, _, student = raw.partition(":")

    label = _TOPIC_LABELS.get(resource, resource.replace("_", " ").title())

    return f"{student} - {label}" if student else label


def _students_in(raw: str) -> list[str]:
    """
    The child names inside one stored `Message.intent` value -
    "attendance:Zoya+fee:Zoya" gives ["Zoya"]. Intents that never
    named a child ("rag", "admin_handoff") give nothing.
    """

    if not raw or raw in ("rag", "cached", "admin_handoff"):
        return []

    names = []
    for part in raw.split("+"):
        _, _, student = part.partition(":")
        student = student.strip()
        if student and student not in names:
            names.append(student)

    return names


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
                print(f"[SessionService] Session created: {session_id} | user_id={user_id}")

                # flush + refresh inside transaction
                await db.flush()
                await db.refresh(new_session)

            # after transaction exits, commit is guaranteed
            # retry mechanism to handle commit visibility
            retries = 3
            saved_session = None
            for attempt in range(retries):
                result = await db.execute(
                    select(session_model.Session).where(session_model.Session.id == session_id)
                )
                saved_session = result.scalar_one_or_none()
                if saved_session:
                    if attempt > 0:
                        print(f"[SessionService] Session found after retry {attempt}")
                    break
                else:
                    if attempt < retries - 1:
                        print(f"[SessionService] Session not visible yet | Retrying...")
                        await asyncio.sleep(0.2)
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Session was committed but could not be found.",
                        )

            print(f"[SessionService] Session verified successfully: {session_id}")

            # publish only once, after verification
            await RabbitMQ().producer(message={"session_id": str(session_id)})
            print(f"[SessionService] Session published to RabbitMQ: {session_id}")

            return saved_session

        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            print(f"[SessionService] Failed to create session: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session",
            )

    # =========================================================
    # GET USER SESSIONS
    # =========================================================
    async def get_user_sessions(self, db: AsyncSession, user_id: UUID, limit: int = 10, skip: int = 0,
                                start: datetime | None = None, end: datetime | None = None):
        rows = await self.session_repo.get_user_sessions(
            db=db, user_id=user_id, limit=limit, skip=skip, start=start, end=end
        )
        return await self._decorate(db=db, sessions=rows)

    # =========================================================
    # DURATION AUR HANDLER
    # =========================================================

    async def _decorate(self, db: AsyncSession, sessions: list):
        """
        Attach duration and handler to each session.

        These two dashboard columns always showed "-" because the API
        never returned the information.

        Escalations are read in a single query rather than one per
        session - otherwise 20 rows would mean 20 queries.
        """

        if not sessions:
            return sessions

        ids = [s.id for s in sessions]

        # Which sessions reached a human.
        # An escalation links to a message, and a message to a session.
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

        # What each session was about. One batched query - not one
        # per session - reading the intent every AI answer already
        # carries (see voice_pipeline.py's message_service.create_message
        # calls). No new column: it is the same `Message.intent` field
        # `handler` above is derived from, just read for its own value
        # here instead of only checking whether a row exists.
        topic_rows = (
            await db.execute(
                select(
                    message_model.Message.session_id,
                    message_model.Message.intent,
                )
                .where(
                    message_model.Message.session_id.in_(ids),
                    message_model.Message.sender_type == SenderTypeEnum.ai,
                    message_model.Message.intent.isnot(None),
                )
                .order_by(message_model.Message.created_at)
            )
        ).all()

        topics_by_session: dict = {}
        for session_id, raw_intent in topic_rows:
            seen = topics_by_session.setdefault(session_id, [])
            if raw_intent and raw_intent not in seen:
                seen.append(raw_intent)

        for row in sessions:
            row.handler = "Human" if row.id in escalated else "AI"

            # A call in progress has no duration - it is still
            # growing. Showing a number for it would be a lie.
            if row.end_at and row.start_at:
                row.duration_seconds = max(
                    0, int((row.end_at - row.start_at).total_seconds())
                )
            else:
                row.duration_seconds = None

            raw_topics = topics_by_session.get(row.id, [])
            formatted = [_format_topic(t) for t in raw_topics]
            formatted = [t for t in formatted if t]

            students: list[str] = []
            for raw in raw_topics:
                for name in _students_in(raw):
                    if name not in students:
                        students.append(name)
            row.students = students

            if not formatted:
                row.topic = None
            elif len(formatted) <= 2:
                row.topic = ", ".join(formatted)
            else:
                row.topic = f"{', '.join(formatted[:2])} +{len(formatted) - 2} more"

        return sessions

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
    async def get_dashboard_stats(self, db: AsyncSession, user_id: UUID,
                                  today_start: datetime | None = None,
                                  week_start: datetime | None = None):
        return {
            "total_calls": await self.session_repo.count_user_sessions(db=db, user_id=user_id),
            "today_calls": await self.session_repo.count_today_sessions(
                db=db, user_id=user_id, today_start=today_start
            ),
            "this_week_calls": await self.session_repo.count_week_sessions(
                db=db, user_id=user_id, week_start=week_start
            ),
        }

    # =========================================================
    # CLOSE USER SESSION
    # =========================================================
    # There are two kinds of caller:
    #   router          -> passes its own injected db
    #   livekit worker  -> has no db session at all
    # So db is optional; when none arrives, one is opened here.
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

    # There is deliberately NO `async with db.begin()` here.
    #
    # The repository's close_session_by_id commits by itself, and then
    # calls refresh(). Wrapping a begin() block around that ends the
    # block's transaction at the commit, and on the very next line
    # SQLAlchemy raises:
    #
    #   "Can't operate on closed transaction inside context manager."
    #
    # The result was that the session did close (the commit had
    # already landed) but the call still ended in an exception: the
    # frontend got a 500 from PATCH /sessions/{id}/close, and every
    # worker teardown printed "[Session Cleanup Error]".
    async def _close(self, db: AsyncSession, user_id: UUID, session_id: UUID):
        session = await self.session_repo.get_by_id(db=db, id=session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if session.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this session")
        return await self.session_repo.close_session_by_id(db=db, session_id=session_id)

    # =========================================================
    # CLOSE SESSION - WORKER (no ownership check)
    # =========================================================
    #
    # The HTTP-facing close above exists to stop one logged-in user
    # from closing another user's session, so it has to check
    # session.user_id against the caller's own JWT-derived user_id.
    #
    # The LiveKit worker is not that caller. It never had the
    # guardian's identity to begin with - LivekitRoomServices is
    # built with user_id=None for every call (make_worker() in
    # livekit_worker.py) - and it only ever closes the one
    # session_id RabbitMQ handed it for this call, so there is
    # nothing to check ownership against in the first place.
    #
    # Before this method existed the worker called the same
    # ownership-checked close() above with user_id=None. Since a
    # real session's owner is never None, `session.user_id != None`
    # was always true, the close always raised 403, and every call
    # ended with the session stuck at status="active" - fixed only
    # much later when start-vocira.ps1 force-closed it at the next
    # restart, which is why closed calls could show hours of
    # "duration".
    async def close_session_internal(
        self,
        session_id: UUID,
        db: AsyncSession | None = None,
    ):
        if db is not None:
            return await self.session_repo.close_session_by_id(db=db, session_id=session_id)

        async with SessionLocal() as own_db:
            return await self.session_repo.close_session_by_id(db=own_db, session_id=session_id)
