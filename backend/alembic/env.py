import asyncio
import os
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env (works both locally and inside the Docker container)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from alembic import context  # type: ignore[attr-defined]
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Alembic Config object, providing .ini file values
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base and all models so Alembic can auto-detect schema changes.
from app.infrastructure.database.base import Base
import app.infrastructure.database.models  # noqa: F401 — registers all models

target_metadata = Base.metadata

# Override sqlalchemy.url from environment variable when present
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection required)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
