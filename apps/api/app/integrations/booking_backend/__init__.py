from __future__ import annotations

from app.integrations.booking_backend.base import BookingBackend, BookingNotFound
from app.integrations.booking_backend.memory import InMemoryBookingBackend

_backend: BookingBackend | None = None


def get_booking_backend() -> BookingBackend:
    global _backend
    if _backend is None:
        _backend = InMemoryBookingBackend()
    return _backend


def set_booking_backend(backend: BookingBackend | None) -> None:
    global _backend
    _backend = backend


__all__ = ["BookingBackend", "BookingNotFound", "InMemoryBookingBackend", "get_booking_backend", "set_booking_backend"]
