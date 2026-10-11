"""In-memory tracking backend with synthetic milestones."""

from __future__ import annotations

from typing import Any

SEED_TRACKING: dict[str, dict[str, Any]] = {
    "BK-100001": {
        "eta": "2026-11-28",
        "milestones": [
            {"event": "Empty container released", "location": "Rotterdam", "timestamp": "2026-10-28T09:00:00Z"},
            {"event": "Gate in at terminal", "location": "Rotterdam", "timestamp": "2026-10-30T14:20:00Z"},
            {"event": "Loaded on vessel", "location": "Rotterdam", "timestamp": "2026-11-02T06:45:00Z"},
        ],
    },
    "BK-100002": {
        "eta": "2026-12-01",
        "milestones": [
            {"event": "Empty container released", "location": "Shanghai", "timestamp": "2026-11-05T03:10:00Z"},
        ],
    },
}


class InMemoryTrackingBackend:
    def __init__(self, seed: dict[str, dict[str, Any]] | None = None) -> None:
        self._data = seed or SEED_TRACKING

    async def milestones(self, shipment_ref: str) -> dict[str, Any]:
        entry = self._data.get(shipment_ref.upper())
        if entry is None:
            return {"shipment_ref": shipment_ref, "milestones": [], "eta": None}
        return {"shipment_ref": shipment_ref.upper(), **entry}

    async def eta(self, shipment_ref: str) -> dict[str, Any]:
        entry = self._data.get(shipment_ref.upper()) or {}
        return {"shipment_ref": shipment_ref.upper(), "eta": entry.get("eta")}
