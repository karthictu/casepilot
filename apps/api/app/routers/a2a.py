"""A2A (agent-to-agent) surface: an agent card for discovery plus `tasks/send` / `tasks/{id}`.

External agents send a natural-language task; the pipeline answers it read-only. A task that needs a write (or an
operator's judgement) comes back `input-required` with a HITL item id, and `tasks/{id}` reflects the outcome once
an operator has reviewed it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.plugin import registry
from app.config import VERSION, settings
from app.database import get_db
from app.models import HitlItem
from app.models import hitl_item as hitl_status
from app.security import Principal, get_principal
from app.services.pipeline_service import run_and_escalate

router = APIRouter(prefix="/a2a", tags=["a2a"])
well_known_router = APIRouter(tags=["a2a"])

# TODO: persist tasks (a table, or Temporal workflow state) for multi-replica deployments.
_TASKS: dict[str, dict[str, Any]] = {}


class Part(BaseModel):
    type: str = "text"
    text: str = ""


class Message(BaseModel):
    role: str = "user"
    parts: list[Part]


class TaskSendParams(BaseModel):
    id: str | None = None
    sessionId: str | None = None  # noqa: N815 — A2A wire name
    message: Message
    metadata: dict[str, Any] = Field(default_factory=dict)


@well_known_router.get("/.well-known/agent.json")
async def agent_card(request: Request) -> dict[str, Any]:
    base = str(request.base_url).rstrip("/")
    return {
        "name": settings.app_name,
        "description": "Case-driven logistics agent: booking and shipment tracking with human-in-the-loop writes.",
        "url": f"{base}/a2a",
        "version": VERSION,
        "capabilities": {"streaming": False, "pushNotifications": False, "stateTransitionHistory": False},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "authentication": {"schemes": ["bearer"] if settings.auth_mode == "jwt" else []},
        "skills": [
            {"id": p.agent_id, "name": p.display_name, "description": p.description, "tags": p.intents}
            for p in registry.list()
        ],
    }


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _task(task_id: str, session_id: str | None, state: str, text: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task_id,
        "sessionId": session_id,
        "status": {
            "state": state,
            "message": {"role": "agent", "parts": [{"type": "text", "text": text}]},
            "timestamp": _now(),
        },
        "artifacts": [{"name": "response", "parts": [{"type": "text", "text": text}]}],
        "metadata": metadata,
    }


@router.post("/tasks/send")
async def tasks_send(
    params: TaskSendParams, db: AsyncSession = Depends(get_db), principal: Principal = Depends(get_principal)
) -> dict[str, Any]:
    text = " ".join(p.text for p in params.message.parts if p.type == "text").strip()
    if not text:
        raise HTTPException(422, "message must contain a text part")
    task_id = params.id or uuid.uuid4().hex
    state, item = await run_and_escalate(db, text, surface="a2a", source_ref=task_id, customer_id=principal.sub)
    orchestrator = state.get("orchestrator_decision") or {}
    metadata = {
        "intent": orchestrator.get("intent"),
        "confidence": orchestrator.get("confidence"),
        "route_to": state.get("route_to"),
        "hitl_item_id": item.id if item else None,
        "owner": principal.sub,
    }
    if item:
        reply = f"{state.get('response_text')} (pending operator approval, item {item.id})"
        task = _task(task_id, params.sessionId, "input-required", reply, metadata)
    elif state.get("error"):
        task = _task(task_id, params.sessionId, "failed", str(state["error"]), metadata)
    else:
        task = _task(task_id, params.sessionId, "completed", state.get("response_text", ""), metadata)
    _TASKS[task_id] = task
    return task


_STATE_FOR_ITEM = {hitl_status.EXECUTED: "completed", hitl_status.REJECTED: "rejected", hitl_status.FAILED: "failed"}


@router.get("/tasks/{task_id}")
async def tasks_get(
    task_id: str, db: AsyncSession = Depends(get_db), principal: Principal = Depends(get_principal)
) -> dict[str, Any]:
    task = _TASKS.get(task_id)
    if task is None or task["metadata"].get("owner") != principal.sub:
        raise HTTPException(404, f"Task {task_id} not found")
    item_id = task["metadata"].get("hitl_item_id")
    if item_id and task["status"]["state"] == "input-required":
        item = await db.get(HitlItem, item_id)
        if item is not None and item.status in _STATE_FOR_ITEM:
            text = f"Operator {item.status} the request." + (
                f" Note: {item.reviewer_note}" if item.reviewer_note else ""
            )
            if item.status == hitl_status.EXECUTED:
                ref = ((item.result or {}).get("result") or {}).get("booking_ref")
                text = f"Approved and executed{f' ({ref})' if ref else ''}."
            task = _task(task_id, task["sessionId"], _STATE_FOR_ITEM[item.status], text, task["metadata"])
            _TASKS[task_id] = task
    return task
