import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.microservices.auth_services.router import (
    auth_router,
    refresh_token_router,
    user_router,
    admin_users_router,
)

from backend.microservices.auth_services.models import (
    user_model,
    role_model,
    refresh_tokken,
    permission_model,
    role_permision_model,
)

from backend.helper_functions.database.engine import create_database_engine
from backend.microservices.auth_services.core.config import settings
from backend.helper_functions.database.base import Base
from sqlalchemy import text


# ============================================================
# Database Engine
# ============================================================

engine = create_database_engine(
    database_url=settings.DATABASE_URL
)


# ============================================================
# Lifespan
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # create_all never adds a column to a table that exists, so the
        # school of an account is added here - once, and harmlessly
        # again on every later start.
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS school_id VARCHAR(40)"
        ))

        # The platform's super admin role (runs every school).
        await conn.execute(text(
            "INSERT INTO role (role_id, name) SELECT 'ROLE-004', 'super_admin' "
            "WHERE NOT EXISTS (SELECT 1 FROM role WHERE name = 'super_admin')"
        ))

    print("Auth service started successfully")

    yield

    logging.critical("Auth Service is shutting down")


# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    lifespan=lifespan
)


# ============================================================
# Routers
# ============================================================

app.include_router(user_router.router)
# The admin panel's Users page - for managing parent accounts.
# It lives in the auth service because password hashing (argon2)
# exists only in this venv.
app.include_router(admin_users_router.router)
app.include_router(refresh_token_router.route)
app.include_router(auth_router.router)