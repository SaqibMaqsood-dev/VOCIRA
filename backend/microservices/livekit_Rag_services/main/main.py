import asyncio
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from huggingface_hub import login

from backend.helper_functions.database import (create_database_engine , Base)



from backend.microservices.livekit_Rag_services.core.config import (
    settings,
)

from backend.microservices.livekit_Rag_services.middleware.correlation_ID import (
    CorrelationMiddleware,
)

from backend.microservices.livekit_Rag_services.middleware.middleware import (
    LoggingMiddleware,
)

from backend.microservices.livekit_Rag_services.middleware.rate_limit_middleware import (
    RateLimitMiddleware,
)

from backend.microservices.livekit_Rag_services.routers.users_route import (
    admin_route,
    session_route,
    escalation_route,
    livekit_router,
    message_route,
    rag_route,
)

from backend.microservices.livekit_Rag_services.routers.users_route.notification_router import (
    router as notification_router,
    notification_manager,
)

from backend.microservices.livekit_Rag_services.core.rabitmq import (
    RabbitMQ,
)


# =========================================================
# DATABASE
# =========================================================

engine = create_database_engine(
    settings.DATABASE_URL
)


# =========================================================
# RABBITMQ
# =========================================================

rabbitmq = RabbitMQ()

notification_consumer_task = None


# =========================================================
# LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    global notification_consumer_task

    # -----------------------------------------------------
    # HuggingFace
    # -----------------------------------------------------

    if settings.HF_TOKEN:
        login(
            token=settings.HF_TOKEN
        )

    # -----------------------------------------------------
    # Database
    # -----------------------------------------------------

    async with engine.begin() as conn:

        await conn.run_sync(
            Base.metadata.create_all
        )

    # -----------------------------------------------------
    # RabbitMQ
    # -----------------------------------------------------

    await rabbitmq.connect()

    # -----------------------------------------------------
    # Start Admin Notification Consumer
    # -----------------------------------------------------

    notification_consumer_task = asyncio.create_task(
        rabbitmq.admin_notification_consumer(
            notification_manager
        )
    )

    print(
        "🔔 Admin notification consumer started"
    )

    print(
        "✅ Application started successfully"
    )

    try:

        yield

    finally:

        # -------------------------------------------------
        # Stop notification consumer
        # -------------------------------------------------

        if notification_consumer_task:

            notification_consumer_task.cancel()

            try:
                await notification_consumer_task

            except asyncio.CancelledError:
                pass

        # -------------------------------------------------
        # Close RabbitMQ connection
        # -------------------------------------------------

        if rabbitmq._connection:

            await rabbitmq._connection.close()

        logging.critical(
            "🛑 Application shutting down"
        )


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    lifespan=lifespan
)


# =========================================================
# MIDDLEWARE
# =========================================================

app.add_middleware(
    LoggingMiddleware
)

app.add_middleware(
    CorrelationMiddleware
)

app.add_middleware(
    RateLimitMiddleware
)


# =========================================================
# ROUTERS
# =========================================================

app.include_router(
    session_route.router,
    prefix="/livekit",
)

app.include_router(
    escalation_route.router,
    prefix="/livekit",
)

# Admin panel ka apna hissa - har endpoint require_admin ke peeche.
app.include_router(
    admin_route.router,
    prefix="/livekit",
)

app.include_router(
    message_route.router,
    prefix="/livekit",
)

# Knowledge base ka intezaam. Pehle ye endpoints thay hi nahi -
# ingestion ka code sirf dead main.py se bulaya jata tha.
app.include_router(
    rag_route.router,
    prefix="/livekit",
)

app.include_router(
    livekit_router.router
)

# ---------------------------------------------------------
# Notification WebSocket
# ---------------------------------------------------------

app.include_router(
    notification_router
)