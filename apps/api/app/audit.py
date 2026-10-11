"""Immutable audit trail. Every decision, escalation, approval and write is recorded here.

`emit` adds an `AuditEvent` to the caller's session (the caller commits with its own unit of work, so the audit
row and the state change land together) and mirrors it to the `casepilot.audit` logger as one JSON line, which
you can ship to any log sink. Payload strings are PII-redacted before they are stored.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.guardrails import redact_value
from app.middleware import request_id_var
from app.models import AuditEvent

logger = logging.getLogger("casepilot.audit")


async def emit(
    db: AsyncSession,
    event_type: str,
    *,
    actor: str,
    surface: str,
    payload: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        actor=actor,
        surface=surface,
        request_id=request_id or request_id_var.get(),
        payload=redact_value(payload or {}),
    )
    db.add(event)
    await db.flush()
    logger.info(json.dumps({"audit": event.to_dict()}, default=str))
    return event
