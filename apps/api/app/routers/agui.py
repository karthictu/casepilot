"""Chat surface: AG-UI over Server-Sent Events, consumed by the admin UI's assistant-ui thread.

The pipeline runs read-only, then its trace is replayed as AG-UI events: steps, tool calls, the answer, and a
`CUSTOM` `hitl` event when the request was escalated.
TODO: stream model tokens as they arrive instead of replaying the finished run.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.protocols import agui_events as ev
from app.security import Principal, get_principal
from app.services.pipeline_service import run_and_escalate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agui", tags=["chat"])


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


def parse_input(body: dict[str, Any]) -> tuple[str, list[dict[str, str]], str, str]:
    """(latest user text, prior history, thread id, run id) from an AG-UI RunAgentInput."""
    messages = [m for m in body.get("messages") or [] if m.get("role") in ("user", "assistant")]
    turns = [{"role": m["role"], "content": _content_text(m.get("content"))} for m in messages]
    last_user = next((i for i in range(len(turns) - 1, -1, -1) if turns[i]["role"] == "user"), None)
    query = turns[last_user]["content"] if last_user is not None else ""
    history = turns[:last_user] if last_user is not None else []
    return query, history[-10:], body.get("threadId") or uuid.uuid4().hex, body.get("runId") or uuid.uuid4().hex


async def build_events(db: AsyncSession, body: dict[str, Any], principal: Principal) -> list[dict[str, Any]]:
    query, history, thread_id, run_id = parse_input(body)
    events = [ev.run_started(thread_id, run_id)]
    if not query.strip():
        return [*events, ev.run_error("No user message")]
    try:
        state, item = await run_and_escalate(
            db, query, surface="chat", source_ref=thread_id, customer_id=principal.sub, history=history
        )
    except Exception as e:
        logger.exception("chat run failed")
        return [*events, ev.run_error(str(e))]

    events += ev.step("orchestrator")
    if state.get("agent_id"):
        events += ev.step(state["agent_id"])
    for call in state.get("tool_calls") or []:
        events += ev.tool_call(
            call["name"],
            call["arguments"],
            call["result"] if not call["error"] else {"error": call["error"]},
            call.get("id") or None,
        )
    events += ev.text_message(state.get("response_text") or "")
    if item:
        events.append(ev.custom("hitl", {"hitl_item_id": item.id, "action": item.action, "reason": item.reason}))
    events.append(ev.run_finished(thread_id, run_id))
    return events


@router.post("")
async def agui(request: Request, db: AsyncSession = Depends(get_db), principal: Principal = Depends(get_principal)):
    events = await build_events(db, await request.json(), principal)

    async def stream() -> AsyncIterator[str]:
        for event in events:
            yield ev.encode_sse(event)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
