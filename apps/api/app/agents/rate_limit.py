"""Per-tool, per-caller sliding-window rate limiting.

An application-layer backstop behind whatever gateway rate limits you run: write tools get strict limits, reads
generous ones. Tools without an entry are unlimited.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class RateLimitConfig:
    max_requests: int
    window_seconds: float


DEFAULT_LIMITS: dict[str, RateLimitConfig] = {
    "booking_create": RateLimitConfig(max_requests=2, window_seconds=1.0),
    "booking_amend": RateLimitConfig(max_requests=2, window_seconds=1.0),
    "booking_cancel": RateLimitConfig(max_requests=2, window_seconds=1.0),
    "booking_status": RateLimitConfig(max_requests=10, window_seconds=1.0),
    "tracking_get_milestones": RateLimitConfig(max_requests=10, window_seconds=1.0),
    "tracking_get_eta": RateLimitConfig(max_requests=10, window_seconds=1.0),
}


@dataclass
class RateLimitResult:
    allowed: bool
    tool: str
    caller: str
    remaining: int = 0
    retry_after_seconds: float = 0.0


class RateLimiter:
    """Thread-safe sliding-window counter keyed by (tool, caller)."""

    def __init__(self, limits: dict[str, RateLimitConfig] | None = None) -> None:
        self._limits = DEFAULT_LIMITS if limits is None else limits
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, tool: str, caller: str) -> RateLimitResult:
        config = self._limits.get(tool)
        if config is None:
            return RateLimitResult(allowed=True, tool=tool, caller=caller, remaining=999)

        key = f"{tool}:{caller}"
        now = time.monotonic()
        with self._lock:
            window = self._windows[key]
            window[:] = [t for t in window if t > now - config.window_seconds]
            if len(window) >= config.max_requests:
                retry = window[0] + config.window_seconds - now
                return RateLimitResult(allowed=False, tool=tool, caller=caller, retry_after_seconds=max(0.0, retry))
            window.append(now)
            return RateLimitResult(allowed=True, tool=tool, caller=caller, remaining=config.max_requests - len(window))

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()


_limiter = RateLimiter()


def get_limiter() -> RateLimiter:
    return _limiter
