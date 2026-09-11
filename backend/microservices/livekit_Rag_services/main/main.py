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
    support_route,
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
    # Best-effort: the broker being down shouldn't stop the whole
    # API from serving. Auth, sessions and CRUD don't need it —
    # only admin notifications and the voice worker handoff do,
    # and those degrade on their own until the broker is back.

    try:

        await rabbitmq.connect()

        notification_consumer_task = asyncio.create_task(
            rabbitmq.admin_notification_consumer(
                notification_manager
            )
        )

        print(
            "Admin notification consumer started"
        )

    except Exception as e:

        notification_consumer_task = None

        print(
            f"WARNING: RabbitMQ unavailable ({e}). "
            "Starting without admin notifications / voice worker handoff."
        )

    print(
        "Application started successfully"
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
            "Application shutting down"
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

# The admin panel's own section - every endpoint behind require_admin.
app.include_router(
    admin_route.router,
    prefix="/livekit",
)

app.include_router(
    message_route.router,
    prefix="/livekit",
)

# Knowledge base management. These endpoints did not exist before -
# the ingestion code was only called from the dead main.py.
app.include_router(
    rag_route.router,
    prefix="/livekit",
)

# Support tickets - these go into ERPNext's Issue doctype.
# The Support page used to be a dead form (there was no fetch at all).
app.include_router(
    support_route.router,
    prefix="/livekit",
)

app.include_router(
    livekit_router.router
)

# ---------------------------------------------------------
# Notification WebSocket
# ---------------------------------------------------------
#
# Same /livekit prefix as every other router here. Without it the
# socket sat at /notifications/... while the gateway maps its own
# /livekit namespace onto the service's - so the gateway could not
# reach it, and the admin panel had to bypass the gateway and talk
# to :8001 directly (which only ever worked on one machine).

app.include_router(
    notification_router,
    prefix="/livekit",
)