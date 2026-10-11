"""LangFuse (SDK 4.x) tracer: every pipeline run is a trace, and every agent, tool call and LLM generation a
nested observation. Works with LangFuse Cloud or a self-hosted server (`CASEPILOT_LANGFUSE_HOST`)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.agents.guardrails import redact_value
from app.config import settings

logger = logging.getLogger(__name__)


class LangfuseTracer:
    def __init__(self) -> None:
        from langfuse import Langfuse

        self._client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            tracing_enabled=settings.langfuse_enabled,
            # Every span input/output/metadata passes through the same PII redaction as the audit trail.
            mask=lambda *, data, **_: redact_value(data),
        )

    @contextmanager
    def span(
        self, name: str, *, as_type: str = "span", input: Any = None, metadata: dict[str, Any] | None = None
    ) -> Iterator[Any]:
        with self._client.start_as_current_observation(
            name=name, as_type=as_type, input=input, metadata=metadata
        ) as observation:
            yield observation

    def flush(self) -> None:
        try:
            self._client.flush()
        except Exception:  # tracing must never break a request
            logger.exception("LangFuse flush failed")
