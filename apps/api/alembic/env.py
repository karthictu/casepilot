"""Alembic environment (async). On Postgres a session-level advisory lock serialises concurrent migrations, so
several replicas can boot at once with migrate-on-start without racing each other."""

from __future__ import annotations

import asyncio

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app import models  # noqa: F401 — registers tables
from app.config import settings
from app.database import Base

target_metadata = Base.metadata
MIGRATION_LOCK_ID = 4815162342


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(settings.database_url, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        postgres = connection.dialect.name == "postgresql"
        if postgres:
            await connection.execute(text(f"SELECT pg_advisory_lock({MIGRATION_LOCK_ID})"))
        try:
            await connection.run_sync(_run)
            await connection.commit()
        finally:
            if postgres:
                await connection.execute(text(f"SELECT pg_advisory_unlock({MIGRATION_LOCK_ID})"))
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
