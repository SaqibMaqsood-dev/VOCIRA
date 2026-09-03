import asyncio
import json
import traceback

import aio_pika
from livekit import api

from backend.microservices.livekit_Rag_services.core.config import settings


class RabbitMQ:

    # =========================================================
    # RabbitMQ CONSTANTS
    # =========================================================

    EXCHANGE_NAME = "vocira.direct"

    # Existing session flow
    SESSION_QUEUE = "vocira_queue"
    SESSION_CREATED_KEY = "session.created"

    # Existing retry / DLQ
    DLQ_QUEUE = "vocira_dld"
    DLQ_KEY = "session.dlq"

    RETRY_QUEUE = "retry_queue"
    RETRY_KEY = "session.retry"

    # New admin notification flow
    ADMIN_NOTIFICATION_QUEUE = "admin_notification_queue"
    ADMIN_HANDOFF_KEY = "admin.call.handoff"

    def __init__(self):

        self._queue = None
        self._channel = None
        self._exchange = None

        self._dlq_queue = None
        self._connection = None
        self._RetryQueue = None

        # New queue
        self._admin_notification_queue = None

    # =========================================================
    # CONNECT
    # =========================================================

    async def connect(self):

        # Reuse existing connection
        if self._connection and not self._connection.is_closed:
            return

        print("[RabbitMQ] Establishing connection to host...")

        self._connection = await aio_pika.connect_robust(
            "amqp://guest:guest@localhost/"
        )

        self._channel = await self._connection.channel()

        await self._channel.set_qos(
            prefetch_count=1
        )

        # =====================================================
        # CREATE EXCHANGE
        # =====================================================

        self._exchange = await self._channel.declare_exchange(
            self.EXCHANGE_NAME,
            aio_pika.ExchangeType.DIRECT,
            durable=True
        )

        # =====================================================
        # EXISTING SESSION QUEUE
        # =====================================================

        self._queue = await self._channel.declare_queue(
            self.SESSION_QUEUE,
            durable=True,
            arguments={
                "x-dead-letter-exchange": self.EXCHANGE_NAME,
                "x-dead-letter-routing-key": self.RETRY_KEY,
            }
        )

        # =====================================================
        # EXISTING DLQ
        # =====================================================

        self._dlq_queue = await self._channel.declare_queue(
            self.DLQ_QUEUE,
            durable=True,
        )

        # =====================================================
        # EXISTING RETRY QUEUE
        # =====================================================

        self._RetryQueue = await self._channel.declare_queue(
            self.RETRY_QUEUE,
            durable=True,
            arguments={
                "x-message-ttl": 30000,
                "x-dead-letter-exchange": self.EXCHANGE_NAME,
                "x-dead-letter-routing-key": self.SESSION_CREATED_KEY,
            }
        )

        # =====================================================
        # NEW ADMIN NOTIFICATION QUEUE
        # =====================================================

        self._admin_notification_queue = (
            await self._channel.declare_queue(
                self.ADMIN_NOTIFICATION_QUEUE,
                durable=True,
            )
        )

        # =====================================================
        # EXISTING BINDINGS
        # =====================================================

        await self._queue.bind(
            self._exchange,
            routing_key=self.SESSION_CREATED_KEY,
        )

        await self._dlq_queue.bind(
            self._exchange,
            routing_key=self.DLQ_KEY,
        )

        await self._RetryQueue.bind(
            self._exchange,
            routing_key=self.RETRY_KEY,
        )

        # =====================================================
        # NEW ADMIN HANDOFF BINDING
        # =====================================================

        await self._admin_notification_queue.bind(
            self._exchange,
            routing_key=self.ADMIN_HANDOFF_KEY,
        )

        print(
            "[RabbitMQ] Channel, Exchange and Queues "
            "successfully initialized."
        )

    # =========================================================
    # EXISTING SESSION PRODUCER
    # =========================================================

    async def producer(
        self,
        message: dict
    ):

        await self.connect()

        msg = aio_pika.Message(
            body=json.dumps(message).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )

        await self._exchange.publish(
            msg,
            routing_key=self.SESSION_CREATED_KEY
        )

        print(
            "[RabbitMQ] Published session.created:",
            message
        )

    # =========================================================
    # NEW ADMIN HANDOFF PRODUCER
    # =========================================================

    async def publish_admin_handoff(
        self,
        message: dict
    ):
        """
        Publish an event when AI hands the call over to admin.
        """

        await self.connect()

        payload = {
            "event": self.ADMIN_HANDOFF_KEY,
            **message,
        }

        msg = aio_pika.Message(
            body=json.dumps(payload).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )

        await self._exchange.publish(
            msg,
            routing_key=self.ADMIN_HANDOFF_KEY
        )

        print(
            "[RabbitMQ] Published admin.call.handoff:",
            payload
        )

    # =========================================================
    # EXISTING SESSION CONSUMER
    # =========================================================

    async def consumer(
        self,
        worker
    ):

        await self.connect()

        async def handler(
            message: aio_pika.IncomingMessage
        ):

            try:

                data = json.loads(
                    message.body
                )

                session_id = data.get(
                    "session_id"
                )

                print(
                    f"📥 [RabbitMQ] Caught Payload! "
                    f"Session ID: {session_id}"
                )

                token = worker.livekit_token(
                    api_key=settings.LIVEKIT_API_KEY,
                    api_secret=settings.LIVEKIT_API_SECRET,
                    room_name=f"room-{session_id}",
                    user_name="agent"
                )

                await worker.connect_worker(
                    token=token,
                    session_id=session_id
                )

                await message.ack()

                print(
                    f"🛑 Session {session_id} "
                    f"completed successfully."
                )

            except Exception as e:

                print(
                    f"[RabbitMQ Error] {e}"
                )

                traceback.print_exc()

                headers = message.headers or {}

                x_death = headers.get(
                    "x-death",
                    []
                )

                retry_count = 0

                for death in x_death:

                    if death.get(
                        "queue"
                    ) == self.SESSION_QUEUE:

                        retry_count = death.get(
                            "count",
                            0
                        )

                        print(
                            f"Retry Count: {retry_count}"
                        )

                        break

                if retry_count >= 3:

                    print(
                        "Maximum retries reached. "
                        "Sending to DLQ..."
                    )

                    await self._exchange.publish(
                        aio_pika.Message(
                            body=message.body,
                            delivery_mode=(
                                aio_pika.DeliveryMode.PERSISTENT
                            ),
                            content_type=(
                                "application/json"
                            ),
                        ),
                        routing_key=self.DLQ_KEY
                    )

                    await message.ack()

                else:

                    print(
                        "Sending message to Retry Queue..."
                    )

                    await message.nack(
                        requeue=False
                    )

        await self._queue.consume(
            handler,
            no_ack=False
        )

        print(
            "[RabbitMQ] Session consumer is running..."
        )

        await asyncio.Future()

    # =========================================================
    # NEW ADMIN NOTIFICATION CONSUMER
    # =========================================================

    async def admin_notification_consumer(
        self,
        notification_manager
    ):
        """
        Consume admin.call.handoff events and send
        them to connected admin WebSocket clients.
        """

        await self.connect()

        async def handler(
            message: aio_pika.IncomingMessage
        ):

            try:

                data = json.loads(
                    message.body
                )

                print(
                    "[RabbitMQ] Admin handoff event received:"
                )

                print(data)

                # Send notification to connected admins
                await notification_manager.broadcast(
                    data
                )

                await message.ack()

                print(
                    "[RabbitMQ] Admin notification "
                    "sent successfully."
                )

            except Exception as e:

                print(
                    "[RabbitMQ Admin Notification Error]",
                    e
                )

                traceback.print_exc()

                await message.nack(
                    requeue=False
                )

        await self._admin_notification_queue.consume(
            handler,
            no_ack=False
        )

        print(
            "[RabbitMQ] Admin notification consumer "
            "is running..."
        )