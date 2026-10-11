"""Append-only audit trail. Rows are never updated or deleted (Postgres enforces it with a trigger)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, JsonType
from app.models._common import iso, new_id, utcnow


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(128))
    surface: Mapped[str] = mapped_column(String(16))  # case_driven | a2a | mcp | chat | admin
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "actor": self.actor,
            "surface": self.surface,
            "request_id": self.request_id,
            "payload": self.payload,
            "created_at": iso(self.created_at),
        }
