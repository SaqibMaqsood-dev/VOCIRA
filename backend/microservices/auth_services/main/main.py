import os
from fastapi import FastAPI
import logging 
from backend.microservices.auth_services.router import auth_router,refresh_token_router,user_router
from contextlib import asynccontextmanager
from backend.microservices.auth_services.models import (
    user_model , role_model , refresh_tokken , permission_model , role_permision_model , user_role_model
)
from backend.helper_functions.database.engine import create_database_engine

from backend.microservices.auth_services.core.config import settings
from backend.helper_functions.database import Base , engine
# from middleware.middleware import LoggingMiddleware
# from middleware.correlation_ID import CorrelationMiddleware
# from middleware.rate_limit_middleware import RateLimitMiddleware



engine = create_database_engine(database_url=settings.DATABASE_URL)


# -------------------------
# Lifespan handler
# -------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    
    # if settings.HF_TOKEN:
    #     login(token=settings.HF_TOKEN)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Auth service  started successfully")
    
    yield  # app runs here

    # 🧹 Shutdown logic (optional cleanup)
    logging.critical("🛑 Auth Service is  shutting down")



# -------------------------
# App init
# -------------------------
app = FastAPI(lifespan=lifespan)

# Middlware 

# app.add_middleware(LoggingMiddleware)
# app.add_middleware(CorrelationMiddleware)
# app.add_middleware(RateLimitMiddleware)

# -------------------------
# Routers
# -------------------------
app.include_router(user_router.router)
app.include_router(refresh_token_router.route)
app.include_router(auth_router.router)
