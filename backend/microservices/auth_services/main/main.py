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

    print("✅ Auth service started successfully")

    yield

    logging.critical("🛑 Auth Service is shutting down")


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
# Admin panel ka Users page - parents ke accounts sambhalne ke liye.
# Ye auth service mein hai kyunke password hashing (argon2) sirf
# yahan ke venv mein mojood hai.
app.include_router(admin_users_router.router)
app.include_router(refresh_token_router.route)
app.include_router(auth_router.router)