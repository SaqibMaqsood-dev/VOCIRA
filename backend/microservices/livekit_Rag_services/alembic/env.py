from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from backend.helper_functions.database.session import get_db
from backend.microservices.livekit_Rag_services.models import escalation_model
from backend.microservices.livekit_Rag_services.models  import session_model
from backend.microservices.livekit_Rag_services.models import message_model
from backend.helper_functions.database import Base

# =========================================================
# ALEMBIC CONFIG
# =========================================================

config = context.config


# =========================================================
# LOGGING
# =========================================================

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# =========================================================
# IMPORT MODELS
# =========================================================
#
# IMPORTANT:
# Alembic must know about all your models before
# using Base.metadata.
#
# Add all model imports here.
#

from backend.microservices.livekit_Rag_services.models.session_model import (
    Session,
)


# =========================================================
# TARGET METADATA
# =========================================================

target_metadata = Base.metadata


# =========================================================
# OFFLINE MIGRATIONS
# =========================================================

def run_migrations_offline() -> None:
    """
    Run migrations in offline mode.

    Alembic generates SQL without connecting
    directly to the database.
    """

    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():

        context.run_migrations()


# =========================================================
# ONLINE MIGRATIONS
# =========================================================

def run_migrations_online() -> None:
    """
    Run migrations in online mode using
    SQLAlchemy AsyncEngine.
    """

    connectable = async_engine_from_config(
        config.get_section(
            config.config_ini_section,
            {},
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async def run_async_migrations():

        async with connectable.connect() as connection:

            await connection.run_sync(
                do_run_migrations
            )

        await connectable.dispose()

    import asyncio

    asyncio.run(
        run_async_migrations()
    )


# =========================================================
# RUN MIGRATIONS WITH SYNC CONNECTION
# =========================================================

def do_run_migrations(connection) -> None:

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():

        context.run_migrations()


# =========================================================
# START ALEMBIC
# =========================================================

if context.is_offline_mode():

    run_migrations_offline()

else:

    run_migrations_online()

