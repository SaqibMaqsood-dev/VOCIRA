from contextlib import asynccontextmanager
from fastapi import FastAPI
from huggingface_hub import login
from backend.helper_functions.database import (
    Base,
    create_database_engine,
)
from backend.microservices.livekit_Rag_services.core.config import settings
from backend.microservices.livekit_Rag_services.core.logging import *
from backend.microservices.livekit_Rag_services.middleware.correlation_ID import (
    CorrelationMiddleware,
)

from backend.microservices.livekit_Rag_services.middleware.middleware import (
    LoggingMiddleware,
)
from backend.microservices.livekit_Rag_services.middleware.rate_limit_middleware import (
    RateLimitMiddleware,
)
# from backend.microservices.livekit_Rag_services.schema.routers.admin_route import (
#     admin_route,
# )
from backend.microservices.livekit_Rag_services.routers.users_route import (
    session_route
)
from backend.microservices.livekit_Rag_services.routers.users_route import escalation_route, livekit_router, message_route


# Service-specific database engine
engine = create_database_engine(
    settings.DATABASE_URL
)
# -------------------------
# Lifespan handler
# -------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    if settings.HF_TOKEN:
        login(token=settings.HF_TOKEN)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Application started successfully")

    yield  # app runs here

    # 🧹 Shutdown logic (optional cleanup)
    logging.critical("🛑 Application shutting down")




# -------------------------
# App init
# -------------------------
app = FastAPI(lifespan=lifespan)

# Middlware 

app.add_middleware(LoggingMiddleware)
app.add_middleware(CorrelationMiddleware)
app.add_middleware(RateLimitMiddleware)

# -------------------------
# Routers
# -------------------------
# app.include_router(admin_route.router)
app.include_router(session_route.router)
app.include_router(escalation_route.router)
app.include_router(message_route.router)
app.include_router(livekit_router.router)

