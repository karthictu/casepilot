"""In-memory booking backend with a few seeded bookings. Swap for a real adapter in production."""

from __future__ import annotations

import copy
import itertools
from datetime import UTC, datetime
from typing import Any

from app.integrations.booking_backend.base import BookingNotFound

_AMENDABLE = {"origin", "destination", "container_type", "container_count", "cargo_ready_date", "commodity"}

SEED_BOOKINGS: dict[str, dict[str, Any]] = {
    "BK-100001": {
        "origin": "Rotterdam",
        "destination": "Singapore",
        "container_type": "40HC",
        "container_count": 2,
        "cargo_ready_date": "2026-11-02",
        "commodity": "machinery parts",
        "status": "confirmed",
    },
    "BK-100002": {
        "origin": "Shanghai",
        "destination": "Los Angeles",
        "container_type": "20GP",
        "container_count": 4,
        "cargo_ready_date": "2026-11-10",
        "commodity": "furniture",
        "status": "confirmed",
    },
    "BK-100003": {
        "origin": "Valencia",
        "destination": "Busan",
        "container_type": "40RF",
        "container_count": 1,
        "cargo_ready_date": "2026-11-20",
        "commodity": "frozen fruit",
        "status": "pending",
    },
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


class InMemoryBookingBackend:
    def __init__(self, seed: dict[str, dict[str, Any]] | None = None) -> None:
        self._bookings = {ref: {"booking_ref": ref, **b} for ref, b in copy.deepcopy(seed or SEED_BOOKINGS).items()}
        self._seq = itertools.count(200001)

    async def create(self, request: dict[str, Any]) -> dict[str, Any]:
        ref = f"BK-{next(self._seq)}"
        booking = {"booking_ref": ref, **request, "status": "confirmed", "created_at": _now()}
        self._bookings[ref] = booking
        return dict(booking)

    async def amend(self, booking_ref: str, changes: dict[str, Any]) -> dict[str, Any]:
        booking = self._require(booking_ref)
        if booking["status"] == "cancelled":
            raise ValueError(f"{booking_ref} is cancelled and cannot be amended")
        unknown = set(changes) - _AMENDABLE
        if unknown:
            raise ValueError(f"Fields cannot be amended: {sorted(unknown)}")
        booking.update(changes, updated_at=_now())
        return dict(booking)

    async def cancel(self, booking_ref: str, reason: str = "") -> dict[str, Any]:
        booking = self._require(booking_ref)
        booking.update(status="cancelled", cancel_reason=reason, updated_at=_now())
        return dict(booking)

    async def get(self, booking_ref: str) -> dict[str, Any]:
        return dict(self._require(booking_ref))

    def _require(self, booking_ref: str) -> dict[str, Any]:
        booking = self._bookings.get(booking_ref.upper())
        if booking is None:
            raise BookingNotFound(f"Booking {booking_ref} not found")
        return booking
