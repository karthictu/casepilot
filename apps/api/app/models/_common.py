from __future__ import annotations

import uuid
from datetime import UTC, datetime


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:  # SQLite drops tzinfo; values are always stored as UTC
        value = value.replace(tzinfo=UTC)
    return value.isoformat()
