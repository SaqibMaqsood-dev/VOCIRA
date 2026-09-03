from typing import Dict

from fastapi import WebSocket


class NotificationManager:

    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}

    # =========================================================
    # CONNECT ADMIN
    # =========================================================

    async def connect(
        self,
        admin_id: str,
        websocket: WebSocket,
    ):
        await websocket.accept()

        self.connections[admin_id] = websocket

        print(
            f"🔌 [WebSocket] Admin connected: {admin_id}"
        )

    # =========================================================
    # DISCONNECT ADMIN
    # =========================================================

    def disconnect(
        self,
        admin_id: str,
    ):
        self.connections.pop(
            admin_id,
            None,
        )

        print(
            f"🔌 [WebSocket] Admin disconnected: {admin_id}"
        )

    # =========================================================
    # SEND TO SPECIFIC ADMIN
    # =========================================================

    async def send_to_admin(
        self,
        admin_id: str,
        message: dict,
    ):
        websocket = self.connections.get(
            admin_id
        )

        if not websocket:
            print(
                f"⚠️ [WebSocket] Admin "
                f"{admin_id} is not connected."
            )

            return

        try:

            await websocket.send_json(
                message
            )

        except Exception as error:

            print(
                f"❌ [WebSocket] Error sending "
                f"to admin {admin_id}: {error}"
            )

            self.disconnect(
                admin_id
            )

    # =========================================================
    # BROADCAST TO ALL ADMINS
    # =========================================================

    async def broadcast(
        self,
        message: dict,
    ):
        """
        Send notification to all connected admins.
        """

        if not self.connections:

            print(
                "⚠️ [WebSocket] "
                "No admins currently connected."
            )

            return

        disconnected = []

        for admin_id, websocket in list(
            self.connections.items()
        ):

            try:

                await websocket.send_json(
                    message
                )

                print(
                    f"📨 [WebSocket] Notification "
                    f"sent to admin: {admin_id}"
                )

            except Exception as error:

                print(
                    f"❌ [WebSocket] Failed to notify "
                    f"admin {admin_id}: {error}"
                )

                disconnected.append(
                    admin_id
                )

        for admin_id in disconnected:

            self.disconnect(
                admin_id
            )


# =========================================================
# SINGLE SHARED INSTANCE
# =========================================================

notification_manager = NotificationManager()