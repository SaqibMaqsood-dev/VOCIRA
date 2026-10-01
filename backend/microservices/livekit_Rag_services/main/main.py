import asyncio
import logging
import os
import sys

# Same reason as livekit_worker.py: Windows' default console
# encoding (cp1252) cannot print Urdu text, and this service shares
# the same groq.py / human_text.py logging as the worker - an admin
# triggering a RAG query or a knowledge sync that logs Urdu content
# would otherwise crash the same way.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.helper_functions.database import (create_database_engine , Base)
from sqlalchemy import text
# Registers the "schools" table (schools added from the admin panel)
# before create_all runs.
from backend.microservices.livekit_Rag_services.models import school_model  # noqa: F401
from backend.microservices.livekit_Rag_services.models import school_connection_model  # noqa: F401



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
    students_route,
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

    # HuggingFace needs no login() call here. huggingface_hub already
    # picks the token up from the HF_TOKEN environment variable - it
    # said so itself on every boot ("HF_TOKEN is set and is the
    # current active token independently from the token you've just
    # configured"). All login() added was a /whoami-v2 round trip on
    # the startup path, which rate-limits aggressively and once took
    # the whole service down with it.
    os.environ.setdefault("HF_TOKEN", settings.HF_TOKEN or "")

    # -----------------------------------------------------
    # Database
    # -----------------------------------------------------

    async with engine.begin() as conn:

        await conn.run_sync(
            Base.metadata.create_all
        )

        # create_all never adds a column to a table that exists: the
        # school of a call is added here, and every call made before
        # schools existed was the first school's.
        await conn.execute(text(
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS school_id VARCHAR(40)"
        ))
        await conn.execute(text(
            "UPDATE sessions SET school_id = 'educators' WHERE school_id IS NULL"
        ))
        # a school defined in code that was removed on the Schools page
        await conn.execute(text(
            "ALTER TABLE schools ADD COLUMN IF NOT EXISTS deleted BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        # the school's own address - its subdomain
        await conn.execute(text(
            "ALTER TABLE schools ADD COLUMN IF NOT EXISTS subdomain VARCHAR(40)"
        ))

    # The first school's ERPNext keys move once from the server settings
    # into its encrypted connection - so it is managed on the Schools page
    # like every other school (services/erp_services/connections.py).
    try:
        from backend.microservices.livekit_Rag_services.services.erp_services import connections

        await connections.adopt_server_erp()
    except Exception as e:
        print(f"WARNING: could not move the first school's ERP keys into its connection ({e}).")

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

    # The live spreadsheet links of the schools whose records are
    # sheets: re-read on a timer (services/erp_services/records_sync.py).
    from backend.microservices.livekit_Rag_services.services.erp_services import records_sync

    records_sync_task = asyncio.create_task(records_sync.run_forever())

    print(
        "Application started successfully"
    )

    try:

        yield

    finally:

        records_sync_task.cancel()
        try:
            await records_sync_task
        except asyncio.CancelledError:
            pass

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

# The logged-in guardian's own children, for the dashboard card.
app.include_router(
    students_route.router,
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