"""Shipment visibility (read-only). Implement `TrackingBackend` against your track-and-trace API."""

from __future__ import annotations

from typing import Any, Protocol


class TrackingBackend(Protocol):
    async def milestones(self, shipment_ref: str) -> dict[str, Any]: ...

    async def eta(self, shipment_ref: str) -> dict[str, Any]: ...
