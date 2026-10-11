"""Where cases come from. Implement `CaseSource` for your CRM / ticketing system / inbox."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class InboundCase:
    external_id: str
    subject: str
    description: str
    from_address: str
    reason: str  # the CRM's "reason for case" value; drives the owned-reason pre-router
    created_at: datetime | None = None


class CaseSource(Protocol):
    async def fetch_new(self, *, since: datetime | None = None, limit: int = 100) -> list[InboundCase]: ...
