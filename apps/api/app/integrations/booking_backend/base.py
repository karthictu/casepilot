"""The system of record for bookings. Implement `BookingBackend` against your booking API."""

from __future__ import annotations

from typing import Any, Protocol


class BookingNotFound(Exception):
    pass


class BookingBackend(Protocol):
    async def create(self, request: dict[str, Any]) -> dict[str, Any]: ...

    async def amend(self, booking_ref: str, changes: dict[str, Any]) -> dict[str, Any]: ...

    async def cancel(self, booking_ref: str, reason: str = "") -> dict[str, Any]: ...

    async def get(self, booking_ref: str) -> dict[str, Any]: ...
