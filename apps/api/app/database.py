"""Async SQLAlchemy engine, session factory and declarative base.

Postgres in dev/prod (asyncpg); SQLite (aiosqlite) works for tests and quick demos.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.config import settings

# JSONB on Postgres, plain JSON elsewhere.
JsonType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    if url.startswith("sqlite"):
        # One shared connection so an in-memory database survives across sessions.
        return create_async_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_async_engine(url, pool_pre_ping=True)


engine = _make_engine(settings.database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request."""
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """A session for code outside a request (Temporal activities, scripts)."""
    async with SessionLocal() as session:
        yield session


async def create_all() -> None:
    from app import models  # noqa: F401 — registers the tables on Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
