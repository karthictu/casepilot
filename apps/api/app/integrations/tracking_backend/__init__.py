from __future__ import annotations

from app.integrations.tracking_backend.base import TrackingBackend
from app.integrations.tracking_backend.memory import InMemoryTrackingBackend

_backend: TrackingBackend | None = None


def get_tracking_backend() -> TrackingBackend:
    global _backend
    if _backend is None:
        _backend = InMemoryTrackingBackend()
    return _backend


def set_tracking_backend(backend: TrackingBackend | None) -> None:
    global _backend
    _backend = backend


__all__ = ["InMemoryTrackingBackend", "TrackingBackend", "get_tracking_backend", "set_tracking_backend"]
