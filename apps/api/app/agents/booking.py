"""Booking agent: create / amend / cancel / status, with confidence-gated HITL.

Shadow-first: in a read-only session the write tools are withheld, so the agent *proposes* the call
(`proposed_call`) instead of making it. The proposal is what an operator approves, and approval runs exactly that
call: the model is not re-run after approval, so what is approved is what executes.

`enforce_invariants` makes the decision trustworthy whatever the model says: "executed" requires a successful
write tool call in this run, and a proposal must name a real write tool.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents import booking_tools  # noqa: F401 — registers the booking tools
from app.agents._json import coerce_to_dict
from app.agents.graphs.loop_guard import loop_guard_node
from app.agents.graphs.mini import guarded_single_node
from app.agents.graphs.nodes import accumulate, clamp_confidence
from app.agents.graphs.state import STRUCTURED_MARKER, AgentState
from app.agents.memory import get_memory
from app.agents.plugin import AgentPlugin, registry
from app.agents.runtime.engine import run_agent
from app.agents.tools import ToolRegistry
from app.agents.types import AgentConfig, AgentResult, OperationType, SessionContext
from app.config import settings

AGENT_ID = "booking"
WRITE_ACTIONS = {"booking_create", "booking_amend", "booking_cancel"}

_PROMPT = """You are the booking agent for a container shipping desk. You create, amend, cancel and look up bookings.

Use the tools you are given. Some write actions may be withheld in this session. If the request needs a write
tool that is not in your tool list, do NOT claim it was done: return outcome "hitl_required" with a
`proposed_call` holding the exact tool name and arguments, so an operator can approve it.

Write actions you may propose:
{proposable}

Return exactly one JSON object and nothing else:
{{"action": "<booking_create|booking_amend|booking_cancel|booking_status|none>",
  "outcome": "<executed|answered|hitl_required|failed>",
  "booking_ref": "<ref or null>", "proposed_call": {{"tool": "...", "arguments": {{...}}}} or null,
  "confidence": <0.0-1.0>, "summary": "<one sentence for the customer>", "reasoning": "<one sentence>"}}"""


def build_prompt() -> str:
    proposable = "\n".join(
        f"- {td.name}: {td.description} Parameters: {json.dumps(td.parameters)}"
        for td in ToolRegistry.write_tools_for(AGENT_ID)
    )
    return _PROMPT.format(proposable=proposable)


def enforce_invariants(decision: dict[str, Any], result: AgentResult, *, write_allowed: bool) -> dict[str, Any]:
    decision = dict(decision)
    decision.setdefault("action", "none")
    decision["confidence"] = clamp_confidence(decision.get("confidence", 0.0))
    writes = [
        tc for tc in result.tool_calls if (td := ToolRegistry.get(tc.name)) and td.operation_type == OperationType.WRITE
    ]
    succeeded = next((tc for tc in writes if tc.error is None), None)

    if succeeded is not None:
        decision["outcome"] = "executed"
        decision["booking_ref"] = (succeeded.result or {}).get("booking_ref") or decision.get("booking_ref")
        decision["executed_call"] = {"tool": succeeded.name, "arguments": succeeded.arguments}
        decision["proposed_call"] = None
    elif decision.get("outcome") == "executed":
        # The model claimed a write that never happened in this run.
        decision["outcome"] = "hitl_required"
        decision["reasoning"] = "Agent reported a write that was not executed; escalating."

    proposal = decision.get("proposed_call")
    if proposal and (not isinstance(proposal, dict) or proposal.get("tool") not in WRITE_ACTIONS):
        decision["proposed_call"] = None
    if decision.get("outcome") not in {"executed", "answered", "hitl_required", "failed"}:
        decision["outcome"] = "hitl_required"
    if result.error and decision["outcome"] != "executed":
        decision["outcome"] = "failed" if not decision.get("proposed_call") else "hitl_required"
        decision.setdefault("reasoning", result.error)
    return decision


async def run_booking_agent(
    query: str,
    *,
    structured_request: dict[str, Any] | None = None,
    write_allowed: bool = False,
    customer_id: str | None = None,
    history: list[dict[str, str]] | None = None,
    model: str | None = None,
) -> tuple[dict[str, Any], AgentResult]:
    content = query
    if structured_request:
        content = f"{query}\n\n{STRUCTURED_MARKER}\n{json.dumps(structured_request)}"
    config = AgentConfig(name=AGENT_ID, model=model or settings.model_reasoning, system_prompt=build_prompt())
    result = await run_agent(
        config,
        [*(history or []), {"role": "user", "content": content}],
        SessionContext(customer_id=customer_id, write_allowed=write_allowed),
    )
    decision = enforce_invariants(coerce_to_dict(result.output), result, write_allowed=write_allowed)
    decision["_diagnostics"] = result.diagnostics()
    return decision, result


async def _remember(customer_id: str | None, decision: dict[str, Any]) -> None:
    call = decision.get("executed_call") or {}
    if not customer_id or call.get("tool") != "booking_create":
        return
    a = call.get("arguments", {})
    await get_memory().add(
        f"Booked {a.get('container_count')}x{a.get('container_type')} from {a.get('origin')} to {a.get('destination')}",
        user_id=customer_id,
    )


async def booking_node(state: AgentState) -> dict[str, Any]:
    write_allowed = bool(state.get("write_allowed", False))
    decision, result = await run_booking_agent(
        state["query"],
        structured_request=state.get("structured_request"),
        write_allowed=write_allowed,
        customer_id=state.get("customer_id"),
        history=state.get("history"),
        model=state.get("model_override"),
    )
    outcome, confidence = decision["outcome"], decision["confidence"]
    threshold = settings.hitl_confidence_threshold
    hitl_required = outcome == "hitl_required" or (outcome != "executed" and confidence < threshold)
    if outcome == "executed":
        await _remember(state.get("customer_id"), decision)

    updates: dict[str, Any] = {
        "agent_id": AGENT_ID,
        "decision": decision,
        "hitl_required": hitl_required,
        "proposed_call": decision.get("proposed_call"),
        "response_text": decision.get("summary")
        if outcome in ("executed", "answered")
        else f"This needs an operator's approval before it can go ahead: {decision.get('reasoning', '')}".strip(),
        **accumulate(state, result),
    }
    if hitl_required:
        updates["hitl_reason"] = decision.get("reasoning") or f"Booking action '{decision['action']}' needs approval"
    return updates


booking_graph = guarded_single_node(loop_guard_node, booking_node)

registry.register(
    AgentPlugin(
        agent_id=AGENT_ID,
        display_name="Booking Agent",
        description="Creates, amends, cancels and looks up container bookings; writes are HITL-gated.",
        version="1.0.0",
        owner_team="booking",
        intents=["create_booking", "amend_booking", "cancel_booking", "get_booking_status"],
        scopes=["booking.create", "booking.amend", "booking.cancel", "booking.read"],
        graph_factory=lambda: booking_graph,
        write_capable=True,
        requires_hitl=True,
        hitl_confidence_threshold=settings.hitl_confidence_threshold,
    )
)
