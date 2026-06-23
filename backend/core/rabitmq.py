import json
import asyncio
import aio_pika
from core.config import settings
import traceback

class RabbitMQ:

    def __init__(self):
        self.connection = None
        self.channel = None
        self.queue = None  # Explicitly track queue instance variable

    async def connect(self):
        # 🚨 IDEMPOTENCY GUARD: If we already have an active connection, reuse it!
        if self.connection and not self.connection.is_closed:
            return

        print("[RabbitMQ] Establishing connection to host...")
        self.connection = await aio_pika.connect_robust(
            "amqp://guest:guest@localhost/"
        )

        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=1)

        self.queue = await self.channel.declare_queue(
            "vocira_queue",
            durable=True
        )
        print("[RabbitMQ] Channel and Queue successfully initialized.")

    async def producer(self, message: dict):
        await self.connect()  # Safely checks state before re-running
        
        msg = aio_pika.Message(
            body=json.dumps(message).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )

        await self.channel.default_exchange.publish(
            msg,
            routing_key="vocira_queue"
        )

    async def consumer(self, worker):
        await self.connect()

        async def handler(message: aio_pika.IncomingMessage):
            try:
                data = json.loads(message.body)
                session_id = data.get("session_id")
                
                print(f"📥 [RabbitMQ] Caught Payload! Session ID: {session_id}")

                token = worker.livekit_token(
                    api_key=settings.API_KEY,
                    api_secret=settings.API_SECRET,
                    room_name=f"room-{session_id}",
                    user_name="agent"
                )
                
                await worker.connect_worker(token=token, session_id=session_id)

                await message.ack()
                print(f"🛑 [RabbitMQ] Call ended for Session {session_id}. Worker is now free.")

            except Exception as e:
                print(f"[RabbitMQ Error] Failed processing message: {e}")
                traceback.print_exc()
                # Reject the message and put it back in the queue if it crashed during setup
                await message.nack(requeue=True)

        # 🚨 Set no_ack=False to ensure RabbitMQ waits for our manual .ack() or .nack()
        await self.queue.consume(handler, no_ack=False)
        print("[RabbitMQ] Consumer is running and waiting for sessions...")
        await asyncio.Future()