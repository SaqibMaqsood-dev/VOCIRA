import os
import sys


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) # D:\vocira_backend\backend\main
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..")) # D:\vocira_backend\backend
ROOT_DIR = os.path.abspath(os.path.join(BACKEND_DIR, "..")) # D:\vocira_backend

# In paths ko top priority par Python sys.path mein insert karein
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
# -------------------------------------------------------------------------

from fastapi import FastAPI
from contextlib import asynccontextmanager
from huggingface_hub import login
from core.config import settings
from database.database import Base, engine

# Routers (Ab paths perfectly clear hain)
from repository.router.users_route import auth, escalation_route, message_route, refresh_route, session_route
from backend.repository.router.users_route import users_route
from backend.repository.router.admin_route import admin_route


# -------------------------
# Lifespan handler
# -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    #  Startup logic
    if settings.HF_TOKEN:
        login(token=settings.HF_TOKEN)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Application started successfully")
    yield  # app runs here

    #  Shutdown logic (optional cleanup)
    print(" Application shutting down")


# -------------------------
# App init
# -------------------------
app = FastAPI(lifespan=lifespan)


# -------------------------
# Routers
# -------------------------
app.include_router(users_route.router)
app.include_router(admin_route.router)
app.include_router(refresh_route.route)
app.include_router(session_route.router)
app.include_router(escalation_route.router)
app.include_router(message_route.router)
app.include_router(auth.router)