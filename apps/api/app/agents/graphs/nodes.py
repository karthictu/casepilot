"""Helpers shared by specialist nodes."""

from __future__ import annotations

from typing import Any

from app.agents.types import AgentResult


def accumulate(state: dict[str, Any], result: AgentResult) -> dict[str, Any]:
    """Cost/token totals and tool-call history after an agent run, merged with what the state already holds."""
    calls = [tc.to_dict() for tc in result.tool_calls]
    return {
        "total_cost_usd": (state.get("total_cost_usd") or 0.0) + result.total_cost_usd,
        "total_input_tokens": (state.get("total_input_tokens") or 0) + result.total_input_tokens,
        "total_output_tokens": (state.get("total_output_tokens") or 0) + result.total_output_tokens,
        "tool_calls": [*(state.get("tool_calls") or []), *calls],
        "recent_tool_calls": [
            *(state.get("recent_tool_calls") or []),
            *({"name": c["name"], "arguments": c["arguments"]} for c in calls),
        ][-10:],
    }


def clamp_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
