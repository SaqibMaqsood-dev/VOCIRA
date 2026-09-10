import json

from fastapi import HTTPException, status, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from livekit.api import AccessToken, VideoGrants

from backend.helper_functions.database.session import SessionLocal

from backend.microservices.livekit_Rag_services.core.config import settings

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

        session = await self.ss_service.create_session(
            db=db,
            user_id=current_user.user_id,
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

        token = (
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
                json.dumps(
                    {
                        "user_id": str(
                            current_user.user_id
                        ),
                        "role": "parent",
                        "type": "user",
                        "session_id": session_id,
                    }
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
        )

    # ============================================================
    # GUEST LIVEKIT TOKEN
    # ============================================================

    async def create_guest_room_token(self):

        async with SessionLocal() as db:

            # ----------------------------------------------------
            # Guest session
            #
            # user_id MUST remain NULL.
            # ----------------------------------------------------

            session = await self.ss_service.create_session(
                db=db,
                user_id=None,
            )

            if not session:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create guest session.",
                )

            session_id = str(session.id)

            room_name = f"room-{session_id}"

            guest_identity = f"guest-{session_id}"

            token = (
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
                    json.dumps(
                        {
                            "user_id": None,
                            "role": "guest",
                            "type": "guest",
                            "session_id": session_id,
                        }
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
                }
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