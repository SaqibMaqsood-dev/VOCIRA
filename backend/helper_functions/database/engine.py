from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine


def create_database_engine(database_url: str) -> AsyncEngine:
    """
    Create and return an async SQLAlchemy engine.
    """

    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

    return engine

	
