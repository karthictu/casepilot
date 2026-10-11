"""Tracing seam. The default `NoopTracer` costs nothing; `CASEPILOT_LANGFUSE_ENABLED=true` swaps in LangFuse.

Usage:
    with get_tracer().span("agent:booking", as_type="agent", input={...}) as span:
        ...
        span.update(output=..., metadata={...})
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol


class Span(Protocol):
    def update(self, **kwargs: Any) -> None: ...


class Tracer(Protocol):
    def span(
        self, name: str, *, as_type: str = "span", input: Any = None, metadata: dict[str, Any] | None = None
    ) -> Any: ...

    def flush(self) -> None: ...


class _NoopSpan:
    def update(self, **kwargs: Any) -> None:
        return None


class NoopTracer:
    @contextmanager
    def span(
        self, name: str, *, as_type: str = "span", input: Any = None, metadata: dict[str, Any] | None = None
    ) -> Iterator[_NoopSpan]:
        yield _NoopSpan()

    def flush(self) -> None:
        return None


_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    global _tracer
    if _tracer is None:
        from app.config import settings

        if settings.langfuse_enabled:
            from app.observability.langfuse_tracer import LangfuseTracer

            _tracer = LangfuseTracer()
        else:
            _tracer = NoopTracer()
    return _tracer


def set_tracer(tracer: Tracer | None) -> None:
    global _tracer
    _tracer = tracer
