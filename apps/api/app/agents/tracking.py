"""Tracking agent: read-only shipment visibility (milestones, ETA). It has no write tools at all."""

from __future__ import annotations

from typing import Any

from app.agents import tracking_tools  # noqa: F401 — registers the tracking tools
from app.agents._json import coerce_to_dict
from app.agents.graphs.loop_guard import loop_guard_node
from app.agents.graphs.mini import guarded_single_node
from app.agents.graphs.nodes import accumulate, clamp_confidence
from app.agents.graphs.state import AgentState
from app.agents.plugin import AgentPlugin, registry
from app.agents.runtime.engine import run_agent
from app.agents.types import AgentConfig, SessionContext
from app.config import settings

AGENT_ID = "tracking"

SYSTEM_PROMPT = """You are the shipment tracking agent for a container shipping desk. Answer questions about where
a shipment is and when it will arrive, using only your tools. Never guess events or dates.
Return exactly one JSON object and nothing else:
{"outcome": "<answered|not_found|hitl_required>", "shipment_ref": "<ref or null>",
 "summary": "<one or two sentences for the customer>", "confidence": <0.0-1.0>}"""


async def tracking_node(state: AgentState) -> dict[str, Any]:
    config = AgentConfig(
        name=AGENT_ID, model=state.get("model_override") or settings.model_reasoning, system_prompt=SYSTEM_PROMPT
    )
    result = await run_agent(
        config,
        [*(state.get("history") or []), {"role": "user", "content": state["query"]}],
        SessionContext(customer_id=state.get("customer_id")),
    )
    decision = coerce_to_dict(result.output)
    decision["confidence"] = clamp_confidence(decision.get("confidence", 0.0))
    decision.setdefault("outcome", "hitl_required" if result.error else "answered")
    decision["_diagnostics"] = result.diagnostics()
    hitl_required = (
        decision["outcome"] == "hitl_required" or decision["confidence"] < settings.hitl_confidence_threshold
    )
    updates: dict[str, Any] = {
        "agent_id": AGENT_ID,
        "decision": decision,
        "hitl_required": hitl_required,
        "response_text": decision.get("summary") or result.error or "",
        **accumulate(state, result),
    }
    if hitl_required:
        updates["hitl_reason"] = decision.get("summary") or "Tracking answer needs operator review"
    return updates


tracking_graph = guarded_single_node(loop_guard_node, tracking_node)

registry.register(
    AgentPlugin(
        agent_id=AGENT_ID,
        display_name="Tracking Agent",
        description="Read-only shipment visibility: milestones and ETA.",
        version="1.0.0",
        owner_team="visibility",
        intents=["track_shipment"],
        scopes=["tracking.read"],
        graph_factory=lambda: tracking_graph,
    )
)
