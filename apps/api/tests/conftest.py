"""Test fixtures. Everything runs offline: in-memory SQLite, mock LLM, mock case source, in-memory backends."""

from __future__ import annotations

import os

os.environ.update(
    {
        "CASEPILOT_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "CASEPILOT_AUTH_MODE": "mock",
        "CASEPILOT_LLM_PROVIDER": "mock",
        "CASEPILOT_AGENT_RUNTIME": "native",
        "CASEPILOT_WRITE_MODE": "shadow",
        "CASEPILOT_TEMPORAL_ENABLED": "false",
        "CASEPILOT_LANGFUSE_ENABLED": "false",
        "CASEPILOT_MEMORY_BACKEND": "inmemory",
        "CASEPILOT_CASE_SOURCE": "mock",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.agents.memory import set_memory  # noqa: E402
from app.agents.memory.inmemory import InMemoryStore  # noqa: E402
from app.agents.plugin import load_plugins  # noqa: E402
from app.agents.rate_limit import get_limiter  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.integrations.booking_backend import InMemoryBookingBackend, set_booking_backend  # noqa: E402
from app.routers import a2a  # noqa: E402

load_plugins()


@pytest.fixture(autouse=True)
async def _fresh_state(monkeypatch):
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    set_booking_backend(InMemoryBookingBackend())
    set_memory(InMemoryStore())
    get_limiter().reset()
    a2a._TASKS.clear()
    monkeypatch.setattr(settings, "write_mode", "shadow")
    monkeypatch.setattr(settings, "agent_runtime", "native")
    monkeypatch.setattr(settings, "temporal_enabled", False)
    yield


@pytest.fixture
async def db():
    async with SessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
