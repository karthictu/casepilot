"""Typed state shared by the pipeline and every specialist graph."""

from __future__ import annotations

from typing import Any, TypedDict

# Marks the JSON block of pre-extracted fields appended to an agent's user message (case-driven path).
STRUCTURED_MARKER = "STRUCTURED_REQUEST:"


class AgentState(TypedDict, total=False):
    # ── Inputs ──────────────────────────────────────────────────────────────
    query: str
    customer_id: str | None
    booking_ref: str | None
    write_allowed: bool  # granted by the platform, never by the model
    history: list[dict[str, str]]
    structured_request: dict[str, Any]  # pre-extracted fields (case-driven path)
    model_override: str | None

    # ── Outputs ─────────────────────────────────────────────────────────────
    orchestrator_decision: dict[str, Any]  # intent, confidence, route_to, reasoning
    route_to: str  # an agent_id, or "hitl"
    agent_id: str  # the specialist that ran
    decision: dict[str, Any]  # the specialist's structured decision
    response_text: str  # human-readable answer for chat / A2A
    tool_calls: list[dict[str, Any]]  # every tool call made in the run (for streaming + audit)

    # ── Control flow ────────────────────────────────────────────────────────
    hitl_required: bool
    hitl_reason: str
    proposed_call: dict[str, Any] | None  # {"tool", "arguments"}: what runs if an operator approves

    # ── Safety / accounting ────────────────────────────────────────────────
    recent_tool_calls: list[dict[str, Any]]
    loop_detected: bool
    error: str | None
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
