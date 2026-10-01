"""
Admin panel ke khule hue realtime channels.

One admin can have several tabs open - the panel on a laptop, with
another tab beside it. Only ONE socket per admin was kept here
before: opening a second tab dropped the first out of the dictionary.
That socket was not closed, it simply stopped receiving anything - so
an open tab went quietly deaf, and never rang.

Each admin therefore now carries a set of all their sockets.

Every notification is about one school's call, and goes to that school's
admins only. It used to go to every admin of every school: a parent's
question rang on another school's panel, which could not even take the
call. An admin's school comes from their token (caller_school); the
platform super admin, who belongs to no school, gets none.
"""

from typing import Dict, Optional, Set

from fastapi import WebSocket


class NotificationManager:

    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}
        # admin_id -> the school whose calls they take
        self.schools: Dict[str, Optional[str]] = {}

    # =========================================================
    # CONNECT ADMIN
    # =========================================================

    async def connect(
        self,
        admin_id: str,
        websocket: WebSocket,
        school: Optional[str],
    ):
        await websocket.accept()

        self.connections.setdefault(
            admin_id,
            set(),
        ).add(websocket)
        self.schools[admin_id] = (school or "").strip().lower() or None

        print(
            f"[WebSocket] Admin connected: {admin_id} of {school or 'no school'} "
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
            self.schools.pop(admin_id, None)

        print(
            f"[WebSocket] Admin disconnected: {admin_id}"
        )

    # =========================================================
    # BROADCAST TO ONE SCHOOL'S ADMINS
    # =========================================================

    async def broadcast(
        self,
        message: dict,
        *,
        school: Optional[str],
    ):
        """
        Send a notification to the connected admins of `school`. Without a
        school it goes to nobody - a call's details must never reach
        another school's admins by default.
        """

        school = (school or "").strip().lower() or None

        if school is None:

            print(
                "[WebSocket] Notification with no school - "
                f"not sent: {message.get('event')}"
            )

            return

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

            if self.schools.get(admin_id) != school:
                continue

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
