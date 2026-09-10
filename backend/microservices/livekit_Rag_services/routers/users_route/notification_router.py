"""
Admin panel ka realtime channel.

This is how an admin learns that a user has asked to speak to a
person (admin.call.handoff), and that another admin has already taken
that call (escalation.claimed).

AUTH:

A browser cannot send headers on a WebSocket, so the JWT arrives in
the query string: ?token=<access_token>. This endpoint used to be
open with no check at all - anyone could write any admin_id into the
URL and listen to every escalation notification (which carry the
user's name and their question). Now:

  - the token is verified
  - the role must be 'admin'
  - admin_id is taken from the TOKEN, not from the URL
"""

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from backend.helper_functions.token_service.access_tokken.verify_tokken import (
    verify_jwt,
)

from backend.helper_functions.token_service.access_tokken.require_admin import (
    ADMIN_ROLES,
)

from backend.microservices.livekit_Rag_services.services.websokets.websocket_manager import (
    notification_manager,
)


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


class _WSAuthError(Exception):
    """verify_jwt has to be given some exception to raise."""


@router.websocket("/ws/admin")
async def admin_notification_websocket(
    websocket: WebSocket,
):
    """
    The admin panel connects here to listen for incoming call
    notifications.

        ws://<host>/livekit/notifications/ws/admin?token=<jwt>
    """

    token = websocket.query_params.get("token")

    if not token:

        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Token required",
        )

        return

    try:

        token_data = verify_jwt(token, _WSAuthError())

    except Exception:

        print("[WebSocket] Invalid token - connection refused.")

        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid token",
        )

        return

    role = (token_data.role or "").strip().lower()

    if role not in ADMIN_ROLES:

        print(
            f"[WebSocket] Non-admin ({role or 'no role'}) "
            f"tried to open the admin channel."
        )

        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Administrators only",
        )

        return

    # Not from the URL - identity always comes from the token
    admin_id = str(token_data.user_id)

    await notification_manager.connect(
        admin_id=admin_id,
        websocket=websocket,
    )

    try:

        while True:

            # Keep WebSocket alive.
            await websocket.receive_text()

    except WebSocketDisconnect:

        # THIS socket only - the admin's other tab stays open
        notification_manager.disconnect(
            admin_id,
            websocket,
        )

    except Exception as error:

        print(
            f"[WebSocket] Connection error: "
            f"{error}"
        )

        notification_manager.disconnect(
            admin_id,
            websocket,
        )
