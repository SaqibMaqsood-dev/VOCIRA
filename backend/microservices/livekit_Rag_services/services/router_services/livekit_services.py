import json
import os

from fastapi import HTTPException, status, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from livekit.api import AccessToken, RoomAgentDispatch, RoomConfiguration, VideoGrants

from backend.helper_functions.database.session import SessionLocal

from backend.microservices.livekit_Rag_services.core.config import settings

# Which voice agent answers a call:
#   "agents" - the LiveKit Agents one (services/agent/worker.py); the call
#              token asks LiveKit to send it into the room. The default.
#   "legacy" - the older RabbitMQ worker (livekit_worker.py), told of each
#              new session and joining the room itself - kept as a fallback
#              (start-vocira.ps1 -LegacyWorker)
VOICE_ENGINE = (os.getenv("VOICE_ENGINE") or "agents").strip().lower()
AGENT_NAME = "vocira"


def with_voice_agent(token: AccessToken, call: dict) -> AccessToken:
    """On the agents engine, the token dispatches the agent with the call's details."""
    if VOICE_ENGINE != "agents":
        return token
    return token.with_room_config(
        RoomConfiguration(
            agents=[RoomAgentDispatch(agent_name=AGENT_NAME, metadata=json.dumps(call))],
            # LiveKit closes a room ~20 s after its last person leaves - an
            # agent does not count - so a caller on a weak link who needed
            # longer to get back found the call gone. The agent waits 30 s
            # (agent/lifecycle.py), as the older worker did; so does the room.
            departure_timeout=30,
        )
    )
from backend.microservices.livekit_Rag_services.services import tenants
from backend.helper_functions.token_service.access_tokken.require_admin import (
    caller_school,
)
from backend.microservices.auth_services.models.user_model import Users

from backend.microservices.livekit_Rag_services.schema.livekit_schema import (
    LiveKitTokenResponse
    )

from backend.microservices.livekit_Rag_services.services.api_service.api_services import (
    APIServices,
)

from backend.microservices.livekit_Rag_services.services.router_services.session_service import (
    SessionService,
)

from backend.microservices.livekit_Rag_services.models.escalation_model import (
    Escalation,
    EscalationStatus,
)

from backend.microservices.livekit_Rag_services.models.message_model import (
    Message,
)

from backend.microservices.livekit_Rag_services.models.session_model import (
    Session,
)


class LivekitServices:

    def __init__(self):

        # From settings.AUTH_SERVICE_URL - 127.0.0.1 was hardcoded
        # here, even though the config already carried this value. On
        # Docker/the server, 127.0.0.1 points at this container
        # itself, not at the auth service.
        self.api_integrate = APIServices(
            endpoint=f"{settings.AUTH_SERVICE_URL.rstrip('/')}/users"
        )

        self.ss_service = SessionService()

    # ============================================================
    # AUTHENTICATED USER / PARENT LIVEKIT TOKEN
    # ============================================================

    async def create_user_room_token(
        self,
        db: AsyncSession,
        current_user,
        request: Request,
    ) -> LiveKitTokenResponse:

        # --------------------------------------------------------
        # Get authenticated user information
        #
        # current_user.user_id comes from the authenticated JWT.
        # We use the existing Auth endpoint:
        # GET /users/{id}
        # --------------------------------------------------------

        user_id = str(current_user.user_id)

        user_record = await self.api_integrate.Fetching_data(
            request=request,
            endpoint=(
                f"{settings.AUTH_SERVICE_URL.rstrip('/')}"
                f"/users/{user_id}"
            ),
        )

        if not user_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # --------------------------------------------------------
        # Create session for authenticated parent
        #
        # IMPORTANT:
        # user_id is stored in Session.
        # This is what later protects call logs.
        # --------------------------------------------------------

        # The guardian's school, from their account - NULL is the first
        # school, as every account made before schools existed.
        # Read in a session of its own: a query on `db` opens a
        # transaction, and create_session() below begins its own on
        # `db` - "A transaction is already begun" failed every call.
        async with SessionLocal() as lookup:
            account_school = await lookup.scalar(
                select(Users.school_id).where(Users.user_id == current_user.user_id)
            )
        await tenants.refresh(force=bool(account_school) and not tenants.is_known(account_school))
        user_school = tenants.get_school(account_school).id

        session = await self.ss_service.create_session(
            db=db,
            user_id=current_user.user_id,
            school_id=user_school,
            notify_worker=VOICE_ENGINE != "agents",
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create voice session.",
            )

        # --------------------------------------------------------
        # Session ID
        # --------------------------------------------------------

        session_id = str(session.id)

        # --------------------------------------------------------
        # LiveKit room
        # --------------------------------------------------------

        room_name = f"room-{session_id}"

        # --------------------------------------------------------
        # Parent identity
        # --------------------------------------------------------

        user_identity = f"user-{current_user.user_id}"

        # --------------------------------------------------------
        # Generate token
        # --------------------------------------------------------

        call = {
            "user_id": str(
                current_user.user_id
            ),
            "role": "parent",
            "type": "user",
            "session_id": session_id,
            "school": user_school,
        }

        token = with_voice_agent(
            AccessToken(
                api_key=settings.LIVEKIT_API_KEY,
                api_secret=settings.LIVEKIT_API_SECRET,
            )
            .with_identity(
                user_identity
            )
            .with_name(
                user_record["name"]
            )
            .with_metadata(
                json.dumps(call)
            )
            .with_grants(
                VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                )
            ),
            call,
        )

        # --------------------------------------------------------
        # Return
        # --------------------------------------------------------

        jwt_token = token.to_jwt()

        print("========================================")
        print("LIVEKIT TOKEN GENERATED")
        print("session_id:", session_id)
        print("room:", room_name)
        print("token exists:", bool(jwt_token))
        print("token length:", len(jwt_token))
        print("========================================")

        return LiveKitTokenResponse(
            session_id=session_id,
            token=jwt_token,
            room=room_name,
            url=settings.LIVEKIT_URL,
            school={"id": user_school, "name": tenants.get_school(user_school).name},
        )

    # ============================================================
    # GUEST LIVEKIT TOKEN
    # ============================================================

    # Only what the pipeline has every piece for - a Whisper
    # language, a prompt instruction, a Piper voice and a greeting.
    SUPPORTED_LANGUAGES = ("en", "ur")

    async def create_guest_room_token(self, language: str | None = None, school: str | None = None):

        # The school comes from the address the guest opened - the
        # school's own subdomain. Without one there is no call: a guest
        # must never land in some other (the default) school.
        await tenants.refresh()
        found = tenants.find_by_address(school)
        if found is None:
            await tenants.refresh(force=True)
            found = tenants.find_by_address(school)
        if found is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Open the assistant from your school's own link.",
            )
        guest_school = found.id

        async with SessionLocal() as db:

            # ----------------------------------------------------
            # Guest session
            #
            # user_id MUST remain NULL.
            # ----------------------------------------------------

            session = await self.ss_service.create_session(
                db=db,
                user_id=None,
                school_id=guest_school,
                notify_worker=VOICE_ENGINE != "agents",
            )

            if not session:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create guest session.",
                )

            session_id = str(session.id)

            room_name = f"room-{session_id}"

            guest_identity = f"guest-{session_id}"

            # A guest has no account to read a preference from, so
            # their choice travels with the token instead. Anything
            # unrecognised falls back to the default rather than
            # being refused - a call is worth more than a strict
            # error over a query parameter.
            chosen = (language or "").strip().lower()

            if chosen not in self.SUPPORTED_LANGUAGES:
                chosen = None

            call = {
                "user_id": None,
                "role": "guest",
                "type": "guest",
                "session_id": session_id,
                "language": chosen,
                "school": guest_school,
            }

            token = with_voice_agent(
                AccessToken(
                    api_key=settings.LIVEKIT_API_KEY,
                    api_secret=settings.LIVEKIT_API_SECRET,
                )
                .with_identity(
                    guest_identity
                )
                .with_name(
                    "Guest"
                )
                .with_metadata(
                    json.dumps(call)
                )
                .with_grants(
                    VideoGrants(
                        room_join=True,
                        room=room_name,
                        can_publish=True,
                        can_subscribe=True,
                    )
                ),
                call,
            )

            # "room" is the real field - both the
            # LiveKitTokenResponse schema and the frontend read it.
            # Only "room_name" was set here before, so a guest call
            # made the frontend report "Backend did not return a
            # valid 'room'". "room_name" is kept for older consumers.
            return {
                "session_id": session_id,
                "room": room_name,
                "room_name": room_name,
                "token": token.to_jwt(),
                "url": settings.LIVEKIT_URL,
                # the school the call really goes to - the page shows it
                "school": {"id": guest_school, "name": tenants.get_school(guest_school).name},
            }

    # ============================================================
    # ADMIN ACCEPT CALL
    # ============================================================

    async def accept_admin_call(
        self,
        db: AsyncSession,
        current_user,
        escalation_id,
    ):

        # ========================================================
        # 1. VERIFY ADMIN
        # ========================================================

        user_role = getattr(
            current_user,
            "role",
            None,
        )

        if hasattr(user_role, "value"):
            user_role = user_role.value

        if str(user_role).strip().lower() != "admin":

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can accept calls.",
            )

        # ========================================================
        # 2. FIND ESCALATION
        # ========================================================

        escalation_result = await db.execute(
            select(Escalation).where(
                Escalation.id == escalation_id
            )
        )

        escalation = escalation_result.scalar_one_or_none()

        if not escalation:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Escalation not found.",
            )

        # ========================================================
        # 3. VERIFY ESCALATION IS PENDING
        # ========================================================

        current_status = getattr(
            escalation.status,
            "value",
            str(escalation.status),
        )

        if str(current_status).strip().lower() != "pending":

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Escalation cannot be accepted "
                    f"because its current status is "
                    f"'{current_status}'."
                ),
            )

        # ========================================================
        # 4. FIND MESSAGE
        # ========================================================

        message_result = await db.execute(
            select(Message).where(
                Message.id == escalation.message_id
            )
        )

        message = message_result.scalar_one_or_none()

        if not message:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Escalation message not found.",
            )

        # ========================================================
        # 5. FIND SESSION
        # ========================================================

        session_result = await db.execute(
            select(Session).where(
                Session.id == message.session_id
            )
        )

        session = session_result.scalar_one_or_none()

        if not session:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice session not found.",
            )

        # A school's admin takes only their own school's calls. Another
        # school's escalation is "not found" - nothing is given away.
        admin_school = caller_school(current_user)
        if admin_school is not None and (session.school_id or tenants.DEFAULT_SCHOOL_ID) != admin_school:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Escalation not found.",
            )

        # ========================================================
        # 6. VERIFY SESSION ACTIVE
        # ========================================================

        session_status = getattr(
            session.status,
            "value",
            str(session.status),
        )

        if str(session_status).strip().lower() != "active":

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The voice session is no longer active.",
            )

        # ========================================================
        # 7. EXISTING LIVEKIT ROOM
        # ========================================================

        session_id = str(session.id)

        room_name = f"room-{session_id}"

        # ========================================================
        # 8. ADMIN IDENTITY
        # ========================================================

        admin_identity = f"admin-{current_user.user_id}"

        admin_name = getattr(
            current_user,
            "name",
            "Admin",
        )

        # ========================================================
        # 9. ADMIN METADATA
        # ========================================================

        admin_metadata = {
            "user_id": str(
                current_user.user_id
            ),
            "role": "admin",
            "type": "admin",
            "session_id": session_id,
        }

        # ========================================================
        # 10. CLAIM THE ESCALATION - ATOMICALLY
        #
        # Two admins can press "Join" at the same moment. The status
        # check above passes for both, because it only reads. So the
        # real claim happens in a single UPDATE carrying its own
        # condition: the status must still be 'pending'.
        #
        # Postgres locks that row, so only ONE of the two updates
        # gets a rowcount of 1 - the other gets 0 and a clean 409.
        # This cannot be left to the frontend.
        # ========================================================

        try:

            claim = await db.execute(
                update(Escalation)
                .where(
                    Escalation.id == escalation_id,
                    Escalation.status == EscalationStatus.pending,
                )
                .values(status=EscalationStatus.open)
            )

            await db.commit()

        except Exception as error:

            await db.rollback()

            print(
                f"Failed to accept escalation: {error}"
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to accept escalation.",
            )

        if claim.rowcount != 1:

            print(
                f"[Escalation] {escalation_id} pehle hi "
                f"kisi aur admin ne le li."
            )

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another admin has already joined this call.",
            )

        print(
            f"[Escalation] {escalation_id} claimed by "
            f"admin {current_user.user_id}"
        )

        # Stops the other admins' ringing - otherwise a call that
        # is already gone keeps ringing on their screens.
        try:

            from backend.microservices.livekit_Rag_services.services.websokets.websocket_manager import (
                notification_manager,
            )

            await notification_manager.broadcast(
                {
                    "event": "escalation.claimed",
                    "escalation_id": str(escalation_id),
                    "session_id": session_id,
                    "admin_id": str(current_user.user_id),
                },
                # the call's own school - its admins are the ones ringing
                school=session.school_id or tenants.DEFAULT_SCHOOL_ID,
            )

        except Exception as error:

            # Only a notification - the claim is done, do not fail the call
            print(
                f"[Escalation] claimed-broadcast fail: {error}"
            )

        # ========================================================
        # 11. ADMIN LIVEKIT TOKEN
        # ========================================================

        token = (
            AccessToken(
                api_key=settings.LIVEKIT_API_KEY,
                api_secret=settings.LIVEKIT_API_SECRET,
            )
            .with_identity(
                admin_identity
            )
            .with_name(
                admin_name
            )
            .with_metadata(
                json.dumps(
                    admin_metadata
                )
            )
            .with_grants(
                VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                )
            )
        )

        # ========================================================
        # 12. RETURN
        # ========================================================

        return {
            "success": True,
            "message": "Call accepted successfully.",
            "escalation_id": str(
                escalation.id
            ),
            "session_id": session_id,
            # As with the guest endpoint, "room" is required here,
            # or the admin panel cannot connect to LiveKit.
            "room": room_name,
            "room_name": room_name,
            "token": token.to_jwt(),
            "url": settings.LIVEKIT_URL,
            "participant_identity": admin_identity,
            "participant_type": "admin",
        }