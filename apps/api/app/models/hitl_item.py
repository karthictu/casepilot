"""A gated action waiting for (or past) operator review."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, JsonType
from app.models._common import iso, new_id, utcnow

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
EXECUTED = "executed"
FAILED = "failed"

# Action for items with no executable tool call: the operator supplies the arguments, or rejects.
MANUAL_REVIEW = "manual_review"


class HitlItem(Base):
    __tablename__ = "hitl_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(16))  # case | a2a | mcp | chat
    source_ref: Mapped[str] = mapped_column(String(64), index=True)
    agent_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    # {"tool": "<name>", "arguments": {...}, "context": {...}}: exactly what runs on approval.
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default=PENDING, index=True)
    customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "source_ref": self.source_ref,
            "agent_id": self.agent_id,
            "action": self.action,
            "payload": self.payload,
            "confidence": self.confidence,
            "reason": self.reason,
            "status": self.status,
            "reviewer": self.reviewer,
            "reviewer_note": self.reviewer_note,
            "result": self.result,
            "workflow_id": self.workflow_id,
            "created_at": iso(self.created_at),
            "reviewed_at": iso(self.reviewed_at),
        }
