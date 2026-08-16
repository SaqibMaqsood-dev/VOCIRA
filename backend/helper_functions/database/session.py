from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from backend.microservices.livekit_Rag_services.core.config import settings
from .engine import create_database_engine

engine = create_database_engine(database_url=settings.DATABASE_URL)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session