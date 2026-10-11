"""Deterministic mock LLM, so the whole platform runs offline and tests are reproducible.

Each agent has a *mock script*, a plain function `(messages, tools) -> LLMResponse` registered with
`@mock_script("<agent name>")`. The built-in scripts live in `mock_scripts.py`; register your own for a new agent.
Scripts behave like a well-behaved model would: they call tools when offered, and propose a write (instead of
pretending to perform it) when the write tool is withheld.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from app.agents.llm.base import LLMResponse

MockScript = Callable[[list[dict[str, Any]], list[dict[str, Any]]], LLMResponse]
_SCRIPTS: dict[str, MockScript] = {}


def mock_script(agent_name: str) -> Callable[[MockScript], MockScript]:
    def decorator(fn: MockScript) -> MockScript:
        _SCRIPTS[agent_name] = fn
        return fn

    return decorator


def _approx_tokens(value: Any) -> int:
    return max(1, len(json.dumps(value, default=str)) // 4)


class MockLLM:
    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        agent_name: str = "",
    ) -> LLMResponse:
        from app.agents.llm import mock_scripts  # noqa: F401 — registers the built-in scripts

        script = _SCRIPTS.get(agent_name)
        if script is None:
            response = LLMResponse(content=json.dumps({"outcome": "unknown", "reasoning": "no mock script"}))
        else:
            response = script(messages, tools or [])
        response.input_tokens = response.input_tokens or _approx_tokens(messages)
        response.output_tokens = response.output_tokens or _approx_tokens(response.content or response.tool_calls)
        response.model = "mock"
        return response
