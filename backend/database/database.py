from sqlalchemy.ext.asyncio import create_async_engine , async_session , async_sessionmaker , AsyncAttrs , AsyncSession
from sqlalchemy.orm import DeclarativeBase
from core import config


engine = create_async_engine(config.settings.Database_URL)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_= AsyncSession, 
    expire_on_commit= False 
)


class Base(AsyncAttrs , DeclarativeBase):
    pass



async def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.close()
