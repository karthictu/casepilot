"""The synchronous pipeline behind A2A and chat: `loop_guard → classify → route → specialist`.

1. The orchestrator classifies the intent; the registry's routing table picks the agent.
2. Confidence below the threshold, or an intent nobody owns → stop with `hitl_required=True`.
3. Otherwise the specialist's graph runs (registry-driven: a new plugin is reachable with no change here).

The caller decides what a `hitl_required` result means for its surface (A2A `input-required`, a HITL item, a chat
notice). Stateless: durability is Temporal's job (see app/temporal).
"""

from __future__ import annotations

from typing import Any

from app.agents.graphs.loop_guard import loop_guard_node
from app.agents.graphs.mini import guarded_routed_pipeline
from app.agents.graphs.state import AgentState
from app.agents.memory import format_for_prompt, get_memory
from app.agents.orchestrator import run_orchestrator
from app.agents.plugin import load_plugins, registry
from app.config import settings
from app.observability.tracer import get_tracer


async def classify_node(state: AgentState) -> dict[str, Any]:
    customer_id = state.get("customer_id")
    memory_block = ""
    if customer_id:
        memory_block = format_for_prompt(await get_memory().search(state["query"], user_id=customer_id))

    decision = await run_orchestrator(
        state["query"],
        customer_id=customer_id,
        history=state.get("history"),
        memory_block=memory_block,
        model=state.get("model_override"),
    )
    route_to, confidence = decision["route_to"], decision["confidence"]
    plugin = registry.get(route_to)
    threshold = plugin.hitl_confidence_threshold if plugin else settings.hitl_confidence_threshold
    hitl_required = route_to == "hitl" or confidence < threshold
    diagnostics = decision.get("_diagnostics", {})
    updates: dict[str, Any] = {
        "orchestrator_decision": decision,
        "route_to": route_to,
        "hitl_required": hitl_required,
        "total_cost_usd": (state.get("total_cost_usd") or 0.0) + diagnostics.get("total_cost_usd", 0.0),
        "total_input_tokens": (state.get("total_input_tokens") or 0) + diagnostics.get("total_input_tokens", 0),
        "total_output_tokens": (state.get("total_output_tokens") or 0) + diagnostics.get("total_output_tokens", 0),
    }
    if hitl_required:
        updates["hitl_reason"] = (
            f"Intent '{decision['intent']}' at confidence {confidence:.2f} (threshold {threshold}) "
            "needs an operator to review"
        )
    return updates


def route(state: AgentState) -> str | None:
    if state.get("hitl_required"):
        return None
    target = state.get("route_to")
    return target if target and registry.is_registered(target) else None


def specialists() -> dict[str, Any]:
    return {p.agent_id: p.graph.ainvoke for p in registry.list()}


pipeline_graph = guarded_routed_pipeline(loop_guard_node, classify_node, route, specialists)


async def run_pipeline(
    query: str,
    *,
    customer_id: str | None = None,
    write_allowed: bool = False,
    history: list[dict[str, str]] | None = None,
    model_override: str | None = None,
) -> AgentState:
    load_plugins()
    initial: AgentState = {
        "query": query,
        "customer_id": customer_id,
        "write_allowed": write_allowed,
        "history": history or [],
        "model_override": model_override,
        "tool_calls": [],
        "total_cost_usd": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }
    with get_tracer().span("pipeline", as_type="chain", input={"query": query}) as span:
        result: AgentState = await pipeline_graph.ainvoke(initial)  # type: ignore[assignment]
        if result.get("loop_detected"):
            result["hitl_required"], result["hitl_reason"] = True, "Agent loop detected"
        if not result.get("response_text"):
            result["response_text"] = (
                "This request needs a person to review it. An operator has been notified."
                if result.get("hitl_required")
                else "Done."
            )
        span.update(output={k: result.get(k) for k in ("route_to", "hitl_required", "response_text")})
    return result
