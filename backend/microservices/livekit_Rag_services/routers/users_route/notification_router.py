from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
)

from backend.microservices.livekit_Rag_services.services.websokets.websocket_manager import (
    notification_manager,
)


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


@router.websocket("/ws/admin/{admin_id}")
async def admin_notification_websocket(
    websocket: WebSocket,
    admin_id: str,
):
    """
    WebSocket connection used by the admin panel
    to receive incoming call notifications.
    """

    await notification_manager.connect(
        admin_id=admin_id,
        websocket=websocket,
    )

    try:

        while True:

            # Keep WebSocket alive.
            await websocket.receive_text()

    except WebSocketDisconnect:

        notification_manager.disconnect(
            admin_id
        )

    except Exception as error:

        print(
            f"❌ [WebSocket] Connection error: "
            f"{error}"
        )

        notification_manager.disconnect(
            admin_id
        )