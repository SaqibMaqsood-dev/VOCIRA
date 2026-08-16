import asyncio
import json
import traceback

import aio_pika
from livekit import api

from backend.microservices.livekit_Rag_services.core.config import settings
class RabbitMQ:


    def __init__(self):
        self._queue               =  None  
        self._channel             =  None
        self._exchange            =  None
        self._dlq_queue           =  None
        self._connection          =  None
        self._RetryQueue          =  None
        self._BindingQueue        =  None
        self._BindingDLQ          =  None
        self._BindingRetryQueue   =  None

    async def connect(self):
        # 🚨 IDEMPOTENCY GUARD: If we already have an active connection, reuse it!
        if self._connection and not self._connection.is_closed:
            return

        print("[RabbitMQ] Establishing connection to host...")
        self._connection = await aio_pika.connect_robust(
            "amqp://guest:guest@localhost/"
        )

        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)

        # creating Queue 
        self._queue = await self._channel.declare_queue(
            "vocira_queue",
            durable=True,
            arguments= {
                "x-dead-letter-exchange"    : "vocira.direct",
                "x-dead-letter-routing-key" : "session.retry",
            }
        )

        # creating DLQ self.queue 
        self._dlq_queue = await self._channel.declare_queue(
            "vocira_dld",
            durable=True,
            )
        

        # creating Retry  self.queue

        self._RetryQueue = await self._channel.declare_queue(
            "retry_queue",
            durable=True,
            arguments={
                "x-message-ttl" : 30000,   #ms -> sec
                "x-dead-letter-exchange"    : "vocira.direct",
                "x-dead-letter-routing-key" : "session.created"
            }
              )


        # Create Exchange 
        self._exchange = await self._channel.declare_exchange(
             "vocira.direct",
             aio_pika.ExchangeType.DIRECT, 
             durable=True
             )

        # Bind Queue with Exchange 
        await self._queue.bind(
            self._exchange,
            routing_key="session.created",
            
            )

        #Bind DLQ with Exchange
        await self._dlq_queue.bind(
            self._exchange,
            routing_key="session.dlq"
        )


        #Bind DLQ with Exchange
        await self._RetryQueue.bind(
            self._exchange,
            routing_key="session.retry"
        )
    
        print("[RabbitMQ] Channel and Queue successfully initialized.")

    async def producer(self, message: dict):
        await self.connect()  
        
        msg = aio_pika.Message(
            body=json.dumps(message).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )

        await self._exchange.publish(
            msg,
            routing_key="session.created"
            )

    async def consumer(self, worker):
        await self.connect()

        async def handler(message: aio_pika.IncomingMessage):
            try:
                data = json.loads(message.body)
                session_id = data.get("session_id")

                print(f"📥 [RabbitMQ] Caught Payload! Session ID: {session_id}")

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

                # Success
                await message.ack()
                print(f"🛑 Session {session_id} completed successfully.")
        
            except Exception as e:

                print(f"[RabbitMQ Error] {e}")
                traceback.print_exc()

                headers = message.headers or {}
                x_death = headers.get("x-death", [])
                retry_count = 0

                for death in x_death :

                  if x_death :
                    if death["queue"] == "vocira_queue":
                        retry_count = death["count"]

                        print(f"Retry Count : {retry_count}")
                        break

                if retry_count >= 3:
                        
                        print("Maximum retries reached. Sending to DLQ...")

                        await self._exchange.publish(
                            aio_pika.Message(
                                body=message.body,
                                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                            ),
                            routing_key="session.dlq"
                        )

                        # Remove original message
                        await message.ack()

                else:
                            
                        print("Sending message to Retry Queue...")

                        # Main Queue -> Retry Queue
                        await message.nack(requeue=False)
                                
        await self._queue.consume(handler, no_ack=False)

        print("[RabbitMQ] Consumer is running...")

        await asyncio.Future()

