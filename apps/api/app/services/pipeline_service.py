"""Run the synchronous pipeline for an interactive surface (A2A, chat) and escalate to HITL when needed.

Interactive surfaces never write directly: the pipeline runs read-only, and any write becomes a HITL proposal.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.agents.graphs.pipeline import run_pipeline
from app.agents.graphs.state import AgentState
from app.models import HitlItem
from app.models.hitl_item import MANUAL_REVIEW
from app.services import hitl


async def run_and_escalate(
    db: AsyncSession,
    query: str,
    *,
    surface: str,
    source_ref: str,
    customer_id: str,
    history: list[dict[str, str]] | None = None,
) -> tuple[AgentState, HitlItem | None]:
    state = await run_pipeline(query, customer_id=customer_id, write_allowed=False, history=history)
    decision: dict[str, Any] = state.get("decision") or {}
    orchestrator: dict[str, Any] = state.get("orchestrator_decision") or {}
    item = None
    if state.get("hitl_required"):
        proposal = state.get("proposed_call") or {}
        item = await hitl.submit(
            db,
            source=surface,
            source_ref=source_ref,
            agent_id=state.get("agent_id") or state.get("route_to") or "orchestrator",
            action=proposal.get("tool") or MANUAL_REVIEW,
            payload={"tool": proposal.get("tool"), "arguments": proposal.get("arguments"), "context": {"query": query}},
            confidence=float(decision.get("confidence", orchestrator.get("confidence", 0.0))),
            reason=state.get("hitl_reason") or "Needs operator review",
            customer_id=customer_id,
            actor=customer_id,
        )
    await audit.emit(
        db,
        f"{surface}.request",
        actor=customer_id,
        surface=surface,
        payload={
            "source_ref": source_ref,
            "intent": orchestrator.get("intent"),
            "route_to": state.get("route_to"),
            "hitl_item_id": item.id if item else None,
            "cost_usd": state.get("total_cost_usd"),
        },
    )
    await db.commit()
    return state, item
