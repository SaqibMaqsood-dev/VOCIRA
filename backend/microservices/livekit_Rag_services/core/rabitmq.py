import asyncio
import json
import traceback
from typing import Optional, Callable, Any
from uuid import UUID

import aio_pika
from sqlalchemy import select

from backend.microservices.livekit_Rag_services.core.config import settings

from backend.helper_functions.database.session import (
    SessionLocal,
)

from backend.microservices.livekit_Rag_services.models import (
    session_model,
)


class RabbitMQ:

    # =========================================================
    # RABBITMQ CONSTANTS
    # =========================================================

    EXCHANGE_NAME = "vocira.direct"

    # ---------------------------------------------------------
    # Session flow
    # ---------------------------------------------------------

    SESSION_QUEUE = "vocira_queue"
    SESSION_CREATED_KEY = "session.created"

    # ---------------------------------------------------------
    # Retry / DLQ
    # ---------------------------------------------------------

    DLQ_QUEUE = "vocira_dld"
    DLQ_KEY = "session.dlq"

    RETRY_QUEUE = "retry_queue"
    RETRY_KEY = "session.retry"

    MAX_RETRIES = 3
    RETRY_TTL = 30000  # 30 seconds

    # ---------------------------------------------------------
    # Admin handoff flow
    # ---------------------------------------------------------

    ADMIN_NOTIFICATION_QUEUE = "admin_notification_queue"
    ADMIN_HANDOFF_KEY = "admin.call.handoff"

    # =========================================================
    # INITIALIZATION
    # =========================================================

    def __init__(self):

        self._connection = None
        self._channel = None
        self._exchange = None

        self._queue = None
        self._dlq_queue = None
        self._retry_queue = None
        self._admin_notification_queue = None

    # =========================================================
    # CONNECTION
    # =========================================================

    async def connect(self):

        if (
            self._connection
            and not self._connection.is_closed
            and self._channel
            and not self._channel.is_closed
        ):
            return

        print("[RabbitMQ] Establishing connection...")

        self._connection = await aio_pika.connect_robust(
            "amqp://guest:guest@localhost/"
        )

        self._channel = await self._connection.channel()

        await self._channel.set_qos(
            prefetch_count=1
        )

        # =====================================================
        # EXCHANGE
        # =====================================================

        self._exchange = await self._channel.declare_exchange(
            self.EXCHANGE_NAME,
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )

        # =====================================================
        # SESSION QUEUE
        # =====================================================

        self._queue = await self._channel.declare_queue(
            self.SESSION_QUEUE,
            durable=True,
            arguments={
                "x-dead-letter-exchange": self.EXCHANGE_NAME,
                "x-dead-letter-routing-key": self.RETRY_KEY,
            },
        )

        # =====================================================
        # DLQ
        # =====================================================

        self._dlq_queue = await self._channel.declare_queue(
            self.DLQ_QUEUE,
            durable=True,
        )

        # =====================================================
        # RETRY QUEUE
        # =====================================================

        self._retry_queue = await self._channel.declare_queue(
            self.RETRY_QUEUE,
            durable=True,
            arguments={
                "x-message-ttl": self.RETRY_TTL,
                "x-dead-letter-exchange": self.EXCHANGE_NAME,
                "x-dead-letter-routing-key": self.SESSION_CREATED_KEY,
            },
        )

        # =====================================================
        # ADMIN NOTIFICATION QUEUE
        # =====================================================

        self._admin_notification_queue = (
            await self._channel.declare_queue(
                self.ADMIN_NOTIFICATION_QUEUE,
                durable=True,
            )
        )

        # =====================================================
        # SESSION QUEUE BINDING
        # =====================================================

        await self._queue.bind(
            self._exchange,
            routing_key=self.SESSION_CREATED_KEY,
        )

        # =====================================================
        # DLQ BINDING
        # =====================================================

        await self._dlq_queue.bind(
            self._exchange,
            routing_key=self.DLQ_KEY,
        )

        # =====================================================
        # RETRY QUEUE BINDING
        # =====================================================

        await self._retry_queue.bind(
            self._exchange,
            routing_key=self.RETRY_KEY,
        )

        # =====================================================
        # ADMIN HANDOFF BINDING
        # =====================================================

        await self._admin_notification_queue.bind(
            self._exchange,
            routing_key=self.ADMIN_HANDOFF_KEY,
        )

        print(
            "[RabbitMQ] Channel, exchange and queues "
            "successfully initialized."
        )

    # =========================================================
    # SESSION PRODUCER
    # =========================================================

    async def producer(
        self,
        message: dict,
    ):
        """
        Publish session.created event.

        Expected payload:

        {
            "session_id": "...",
            "user_id": "...",
            "user_role": "user"
        }

        Guest:

        {
            "session_id": "...",
            "user_id": null,
            "user_role": "guest"
        }
        """

        await self.connect()

        if not isinstance(message, dict):

            raise ValueError(
                "RabbitMQ producer message must be a dictionary."
            )

        # =====================================================
        # SESSION ID
        # =====================================================

        session_id = message.get(
            "session_id"
        )

        if not session_id:

            raise ValueError(
                "session_id is required for session.created event."
            )

        # =====================================================
        # USER ID
        # =====================================================

        user_id = message.get(
            "user_id"
        )

        if user_id is not None:

            try:

                UUID(
                    str(user_id)
                )

            except (
                ValueError,
                TypeError,
            ):

                raise ValueError(
                    "user_id must be a valid UUID or None."
                )

        # =====================================================
        # ROLE
        # =====================================================

        user_role = message.get(
            "user_role"
        )

        if user_role is None:

            user_role = (
                "guest"
                if user_id is None
                else "user"
            )

        user_role = str(
            user_role
        ).strip().lower()

        # =====================================================
        # NORMALIZED PAYLOAD
        # =====================================================

        payload = {
            "session_id": str(session_id),
            "user_id": (
                str(user_id)
                if user_id is not None
                else None
            ),
            "user_role": user_role,
        }

        msg = aio_pika.Message(
            body=json.dumps(
                payload
            ).encode("utf-8"),
            delivery_mode=(
                aio_pika.DeliveryMode.PERSISTENT
            ),
            content_type="application/json",
        )

        await self._exchange.publish(
            msg,
            routing_key=self.SESSION_CREATED_KEY,
        )

        print(
            "[RabbitMQ] Published session.created:",
            payload,
        )

    # =========================================================
    # ADMIN HANDOFF PRODUCER
    # =========================================================

    async def publish_admin_handoff(
        self,
        message: dict,
    ):

        await self.connect()

        if not isinstance(message, dict):

            raise ValueError(
                "Admin handoff message must be a dictionary."
            )

        payload = {
            "event": self.ADMIN_HANDOFF_KEY,
            **message,
        }

        msg = aio_pika.Message(
            body=json.dumps(
                payload
            ).encode("utf-8"),
            delivery_mode=(
                aio_pika.DeliveryMode.PERSISTENT
            ),
            content_type="application/json",
        )

        await self._exchange.publish(
            msg,
            routing_key=self.ADMIN_HANDOFF_KEY,
        )

        print(
            "[RabbitMQ] Published admin.call.handoff:",
            payload,
        )

    # =========================================================
    # GET RETRY COUNT
    # =========================================================

    def _get_retry_count(
        self,
        message: aio_pika.IncomingMessage,
    ) -> int:

        headers = message.headers or {}

        x_death = headers.get(
            "x-death",
            [],
        )

        if not isinstance(
            x_death,
            list,
        ):

            return 0

        retry_count = 0

        for death in x_death:

            if not isinstance(
                death,
                dict,
            ):

                continue

            queue = death.get(
                "queue"
            )

            count = death.get(
                "count",
                0,
            )

            if queue == self.RETRY_QUEUE:

                try:

                    retry_count = max(
                        retry_count,
                        int(count),
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    pass

        return retry_count

    # =========================================================
    # SEND MESSAGE TO DLQ
    # =========================================================

    async def _send_to_dlq(
        self,
        message: aio_pika.IncomingMessage,
    ):

        await self._exchange.publish(
            aio_pika.Message(
                body=message.body,
                delivery_mode=(
                    aio_pika.DeliveryMode.PERSISTENT
                ),
                content_type="application/json",
            ),
            routing_key=self.DLQ_KEY,
        )

        await message.ack()

        print(
            "[RabbitMQ] Message moved to DLQ."
        )

    # =========================================================
    # GET SESSION USER INFORMATION
    # =========================================================

    async def _get_session_identity(
        self,
        session_id: UUID,
    ) -> tuple[Optional[UUID], str]:
        """
        Fallback identity lookup.

        If RabbitMQ event does not contain user_id,
        retrieve it directly from the database using
        session_id.
        """

        async with SessionLocal() as db:

            result = await db.execute(

                select(
                    session_model.Session
                ).where(

                    session_model.Session.id
                    == session_id
                )
            )

            session = (
                result.scalar_one_or_none()
            )

            if not session:

                raise ValueError(
                    f"Session not found in database: "
                    f"{session_id}"
                )

            database_user_id = (
                session.user_id
            )

            # -------------------------------------------------
            # Determine role
            # -------------------------------------------------

            if database_user_id is None:

                user_role = "guest"

            else:

                user_role = "user"

            print("=" * 70)

            print(
                "🔎 [RabbitMQ] Database session identity lookup"
            )

            print(
                f"🆔 Session ID : {session.id}"
            )

            print(
                f"👤 User ID    : {database_user_id}"
            )

            print(
                f"🔐 Role        : {user_role}"
            )

            print("=" * 70)

            return (
                database_user_id,
                user_role,
            )

    # =========================================================
    # SESSION CONSUMER
    # =========================================================

    async def consumer(
        self,
        worker_factory: Callable[..., Any],
    ):
       

        await self.connect()

        async def handler(
            message: aio_pika.IncomingMessage,
        ):

            try:

                # =================================================
                # DECODE MESSAGE
                # =================================================

                data = json.loads(
                    message.body.decode(
                        "utf-8"
                    )
                )

                if not isinstance(
                    data,
                    dict,
                ):

                    raise ValueError(
                        "RabbitMQ session payload "
                        "must be an object."
                    )

                # =================================================
                # SESSION ID
                # =================================================

                raw_session_id = data.get(
                    "session_id"
                )

                if not raw_session_id:

                    raise ValueError(
                        "session_id missing from "
                        "RabbitMQ message."
                    )

                try:

                    session_id = UUID(
                        str(raw_session_id)
                    )

                except (
                    ValueError,
                    TypeError,
                ):

                    raise ValueError(
                        f"Invalid session_id: "
                        f"{raw_session_id}"
                    )

                # =================================================
                # EVENT USER ID
                # =================================================

                raw_user_id = data.get(
                    "user_id"
                )

                event_user_id: Optional[UUID] = None

                if raw_user_id is not None:

                    try:

                        event_user_id = UUID(
                            str(raw_user_id)
                        )

                    except (
                        ValueError,
                        TypeError,
                    ):

                        raise ValueError(
                            f"Invalid user_id in "
                            f"RabbitMQ message: "
                            f"{raw_user_id}"
                        )

                # =================================================
                # EVENT ROLE
                # =================================================

                event_user_role = data.get(
                    "user_role"
                )

                if event_user_role:

                    event_user_role = str(
                        event_user_role
                    ).strip().lower()

                # =================================================
                # RESOLVE IDENTITY
                # =================================================

                if event_user_id is not None:

                    user_id = event_user_id

                    user_role = (
                        event_user_role
                        or "user"
                    )

                    print(
                        "✅ [RabbitMQ] "
                        "User identity received "
                        "directly from event."
                    )

                else:

                    print(
                        "⚠️ [RabbitMQ] "
                        "user_id missing from event."
                    )

                    print(
                        "🔎 [RabbitMQ] "
                        "Resolving identity from database..."
                    )

                    (
                        database_user_id,
                        database_role,
                    ) = await self._get_session_identity(
                        session_id
                    )

                    user_id = database_user_id

                    user_role = (
                        event_user_role
                        or database_role
                    )

                # =================================================
                # FINAL SECURITY CHECK
                # =================================================

                if user_id is not None:

                    print(
                        "🔐 [RabbitMQ] "
                        "Authenticated session confirmed."
                    )

                    print(
                        f"   User ID : {user_id}"
                    )

                    print(
                        f"   Role    : {user_role}"
                    )

                else:

                    print(
                        "👤 [RabbitMQ] "
                        "Guest session confirmed."
                    )

                    user_role = "guest"

              

                session_worker = worker_factory(
                    user_id=(
                        str(user_id)
                        if user_id is not None
                        else None
                    ),
                    user_role=user_role,
                )

                print("=" * 70)

                print(
                    "🚀 [RabbitMQ] Creating LiveKit "
                    "worker for session"
                )

                print(
                    f"🆔 Session ID : {session_id}"
                )

                print(
                    f"👤 User ID    : "
                    f"{session_worker.user_id}"
                )

                print(
                    f"🔐 User Role  : "
                    f"{session_worker.user_role}"
                )

                print("=" * 70)

                # =================================================
                # GENERATE LIVEKIT TOKEN
                # =================================================

                token = session_worker.livekit_token(

                    api_key=settings.LIVEKIT_API_KEY,

                    api_secret=settings.LIVEKIT_API_SECRET,

                    room_name=(
                        f"room-{session_id}"
                    ),

                    user_name="agent",
                )

                # =================================================
                # CONNECT WORKER
                # =================================================

                await session_worker.connect_worker(

                    token=token,

                    session_id=session_id,
                )

                # =================================================
                # ACK ONLY AFTER SESSION LIFECYCLE COMPLETES
                # =================================================

                await message.ack()

                print(
                    f"✅ [RabbitMQ] Session "
                    f"{session_id} "
                    f"finished successfully."
                )

            except Exception as e:

                print("=" * 70)

                print(
                    "❌ [RabbitMQ Session Error]"
                )

                print(
                    f"Error: {e}"
                )

                traceback.print_exc()

                print("=" * 70)

                # =================================================
                # RETRY COUNT
                # =================================================

                retry_count = (
                    self._get_retry_count(
                        message
                    )
                )

                print(
                    f"[RabbitMQ] "
                    f"Retry Count: "
                    f"{retry_count}"
                )

                # =================================================
                # MAX RETRIES
                # =================================================

                if (
                    retry_count
                    >= self.MAX_RETRIES
                ):

                    print(
                        "[RabbitMQ] "
                        "Maximum retries reached. "
                        "Sending message to DLQ..."
                    )

                    try:

                        await self._send_to_dlq(
                            message
                        )

                    except Exception as dlq_error:

                        print(
                            "[RabbitMQ DLQ Error]",
                            dlq_error,
                        )

                        traceback.print_exc()

                        try:

                            await message.nack(
                                requeue=True
                            )

                        except Exception:

                            pass

                # =================================================
                # RETRY
                # =================================================

                else:

                    print(
                        "[RabbitMQ] "
                        "Sending message "
                        "to retry queue..."
                    )

                    try:

                        await message.nack(
                            requeue=False
                        )

                    except Exception as nack_error:

                        print(
                            "[RabbitMQ NACK Error]",
                            nack_error,
                        )

                        traceback.print_exc()

        # =========================================================
        # START CONSUMER
        # =========================================================

        await self._queue.consume(
            handler,
            no_ack=False,
        )

        print(
            "[RabbitMQ] "
            "Session consumer is running..."
        )

        # Keep worker alive
        await asyncio.Future()

    # =========================================================
    # ADMIN NOTIFICATION CONSUMER
    # =========================================================

    async def admin_notification_consumer(
        self,
        notification_manager,
    ):

        await self.connect()

        async def handler(
            message: aio_pika.IncomingMessage,
        ):

            try:

                data = json.loads(
                    message.body.decode(
                        "utf-8"
                    )
                )

                if not isinstance(
                    data,
                    dict,
                ):

                    raise ValueError(
                        "Admin handoff payload "
                        "must be an object."
                    )

                print(
                    "[RabbitMQ] "
                    "Admin handoff event received:"
                )

                print(
                    data
                )

                await notification_manager.broadcast(
                    data
                )

                await message.ack()

                print(
                    "[RabbitMQ] "
                    "Admin notification "
                    "sent successfully."
                )

            except Exception as e:

                print(
                    "[RabbitMQ Admin Notification Error]",
                    e,
                )

                traceback.print_exc()

                try:

                    await message.nack(
                        requeue=False
                    )

                except Exception:

                    pass

        await self._admin_notification_queue.consume(
            handler,
            no_ack=False,
        )

        print(
            "[RabbitMQ] "
            "Admin notification consumer "
            "is running."
        )

    # =========================================================
    # CLOSE
    # =========================================================

    async def close(self):

        if self._connection:

            try:

                if not self._connection.is_closed:

                    await self._connection.close()

                    print(
                        "[RabbitMQ] "
                        "Connection closed."
                    )

            except Exception as e:

                print(
                    "[RabbitMQ] "
                    "Error while closing connection:",
                    e,
                )

            finally:

                self._connection = None
                self._channel = None
                self._exchange = None

                self._queue = None
                self._dlq_queue = None
                self._retry_queue = None
                self._admin_notification_queue = None
