"""
Admin panel ke khule hue realtime channels.

One admin can have several tabs open - the panel on a laptop, with
another tab beside it. Only ONE socket per admin was kept here
before: opening a second tab dropped the first out of the dictionary.
That socket was not closed, it simply stopped receiving anything - so
an open tab went quietly deaf, and never rang.

Each admin therefore now carries a set of all their sockets.
"""

from typing import Dict, Optional, Set

from fastapi import WebSocket


class NotificationManager:

    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}

    # =========================================================
    # CONNECT ADMIN
    # =========================================================

    async def connect(
        self,
        admin_id: str,
        websocket: WebSocket,
    ):
        await websocket.accept()

        self.connections.setdefault(
            admin_id,
            set(),
        ).add(websocket)

        print(
            f"[WebSocket] Admin connected: {admin_id} "
            f"({len(self.connections[admin_id])} open)"
        )

    # =========================================================
    # DISCONNECT ADMIN
    # =========================================================

    def disconnect(
        self,
        admin_id: str,
        websocket: Optional[WebSocket] = None,
    ):
        """
        Given a websocket, only that socket is removed - the admin's
        other tabs stay open. Given none, all of the admin's go.
        """

        sockets = self.connections.get(admin_id)

        if not sockets:
            return

        if websocket is None:
            sockets.clear()
        else:
            sockets.discard(websocket)

        if not sockets:
            self.connections.pop(
                admin_id,
                None,
            )

        print(
            f"[WebSocket] Admin disconnected: {admin_id}"
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
                "[WebSocket] "
                "No admins currently connected."
            )

            return

        dead = []

        for admin_id, sockets in list(
            self.connections.items()
        ):

            for websocket in list(sockets):

                try:

                    await websocket.send_json(
                        message
                    )

                    print(
                        f"[WebSocket] Notification "
                        f"sent to admin: {admin_id}"
                    )

                except Exception as error:

                    print(
                        f"[WebSocket] Failed to notify "
                        f"admin {admin_id}: {error}"
                    )

                    dead.append(
                        (admin_id, websocket)
                    )

        for admin_id, websocket in dead:

            self.disconnect(
                admin_id,
                websocket,
            )


# =========================================================
# SINGLE SHARED INSTANCE
# =========================================================

notification_manager = NotificationManager()
