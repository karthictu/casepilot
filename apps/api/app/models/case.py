"""An inbound customer case pulled from the CRM, plus the platform's processing overlay."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, JsonType
from app.models._common import iso, new_id, utcnow

# Processing statuses
NEW = "new"
SKIPPED = "skipped"  # reason not owned by this platform
PROCESSING = "processing"
HITL_REQUIRED = "hitl_required"
BOOKED = "booked"
FAILED = "failed"
REJECTED = "rejected"  # operator rejected the proposal


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    from_address: Mapped[str] = mapped_column(String(320), default="")
    reason: Mapped[str] = mapped_column(String(100), default="", index=True)
    status: Mapped[str] = mapped_column(String(32), default=NEW, index=True)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    booking_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hitl_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "external_id": self.external_id,
            "subject": self.subject,
            "description": self.description,
            "from_address": self.from_address,
            "reason": self.reason,
            "status": self.status,
            "intent": self.intent,
            "confidence": self.confidence,
            "booking_ref": self.booking_ref,
            "hitl_item_id": self.hitl_item_id,
            "result": self.result,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
