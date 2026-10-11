"""Human-in-the-loop queue: submit a gated action, review it, execute exactly what was approved.

An item's `payload` is `{"tool", "arguments", "context"}`. On approval the platform runs that tool call with
write permission through the same gate every other call uses. The model is not consulted again, so what the
operator approved is what runs. An operator may correct the arguments (or, for a `manual_review` item, supply the
tool and arguments) as part of approving.

With Temporal enabled, an item that belongs to a workflow is finalised by the workflow (signalled on review),
which gives run-once execution even if the API process dies mid-approval.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.agents.runtime.gate import execute_gated
from app.agents.tools import ToolRegistry
from app.config import settings
from app.models import Case, HitlItem
from app.models import case as case_status
from app.models import hitl_item as hitl_status
from app.models._common import utcnow
from app.services.errors import Conflict, Invalid, NotFound

logger = logging.getLogger(__name__)


async def submit(
    db: AsyncSession,
    *,
    source: str,
    source_ref: str,
    agent_id: str,
    action: str,
    payload: dict[str, Any],
    confidence: float,
    reason: str,
    customer_id: str | None = None,
    workflow_id: str | None = None,
    actor: str = "system",
) -> HitlItem:
    item = HitlItem(
        source=source,
        source_ref=source_ref,
        agent_id=agent_id,
        action=action,
        payload=payload,
        confidence=confidence,
        reason=reason,
        customer_id=customer_id,
        workflow_id=workflow_id,
    )
    db.add(item)
    await db.flush()
    await audit.emit(
        db,
        "hitl.submitted",
        actor=actor,
        surface=source if source != "case" else "case_driven",
        payload={
            "hitl_item_id": item.id,
            "action": action,
            "agent_id": agent_id,
            "confidence": confidence,
            "reason": reason,
            "source_ref": source_ref,
        },
    )
    return item


async def get(db: AsyncSession, item_id: str) -> HitlItem:
    item = await db.get(HitlItem, item_id)
    if item is None:
        raise NotFound(f"HITL item {item_id} not found")
    return item


async def list_items(db: AsyncSession, status: str | None = None, limit: int = 200) -> list[HitlItem]:
    q = select(HitlItem).order_by(HitlItem.created_at.desc()).limit(limit)
    if status:
        q = q.where(HitlItem.status == status)
    return list((await db.execute(q)).scalars())


async def review(
    db: AsyncSession,
    item_id: str,
    *,
    decision: str,
    reviewer: str,
    note: str | None = None,
    tool: str | None = None,
    arguments: dict[str, Any] | None = None,
) -> HitlItem:
    item = await get(db, item_id)
    if item.status != hitl_status.PENDING:
        raise Conflict(f"HITL item {item_id} is already {item.status}")
    if decision not in ("approve", "reject"):
        raise Invalid("decision must be 'approve' or 'reject'")

    if decision == "approve":
        payload = dict(item.payload or {})
        if tool or arguments is not None:
            payload["original"] = {"tool": payload.get("tool"), "arguments": payload.get("arguments")}
            payload["tool"] = tool or payload.get("tool")
            payload["arguments"] = arguments if arguments is not None else payload.get("arguments")
        if not payload.get("tool") or ToolRegistry.get(payload["tool"]) is None:
            raise Invalid("Nothing to execute: approve with a valid `tool` and `arguments`, or reject the item")
        item.payload = payload

    item.status = hitl_status.APPROVED if decision == "approve" else hitl_status.REJECTED
    item.reviewer, item.reviewer_note, item.reviewed_at = reviewer, note, utcnow()
    await audit.emit(
        db,
        f"hitl.{item.status}",
        actor=reviewer,
        surface="admin",
        payload={"hitl_item_id": item.id, "action": item.action, "note": note, "payload": item.payload},
    )

    if item.workflow_id and settings.temporal_enabled:
        await db.commit()
        from app.temporal.client import signal_review

        try:
            await signal_review(item.workflow_id, item.id)
            return item
        except Exception:
            # The workflow is gone (timed out, terminated): finalise here so the item never sticks at "approved".
            logger.warning("Workflow %s not signalable; finalising HITL item %s inline", item.workflow_id, item.id)

    await finalize(db, item)
    await db.commit()
    return item


async def finalize(db: AsyncSession, item: HitlItem) -> HitlItem:
    """Run an approved item's tool call (once) and propagate the outcome to the linked case."""
    if item.status == hitl_status.APPROVED:
        payload = item.payload or {}
        call = await execute_gated(
            payload["tool"], payload.get("arguments") or {}, write_allowed=True, caller=item.customer_id
        )
        item.result = call.to_dict()
        item.status = hitl_status.EXECUTED if call.error is None else hitl_status.FAILED
        await audit.emit(
            db,
            f"hitl.{item.status}",
            actor=item.reviewer or "system",
            surface="admin",
            payload={
                "hitl_item_id": item.id,
                "tool": call.name,
                "error": call.error,
                "booking_ref": (call.result or {}).get("booking_ref") if isinstance(call.result, dict) else None,
            },
        )
    await _sync_case(db, item)
    return item


async def _sync_case(db: AsyncSession, item: HitlItem) -> None:
    if item.source != "case":
        return
    case = await db.get(Case, item.source_ref)
    if case is None:
        return
    if item.status == hitl_status.EXECUTED:
        case.status = case_status.BOOKED
        result = (item.result or {}).get("result") or {}
        case.booking_ref = result.get("booking_ref") or case.booking_ref
    elif item.status == hitl_status.FAILED:
        case.status = case_status.FAILED
    elif item.status == hitl_status.REJECTED:
        case.status = case_status.REJECTED
    await audit.emit(
        db,
        f"case.{case.status}",
        actor=item.reviewer or "system",
        surface="case_driven",
        payload={"case_id": case.id, "hitl_item_id": item.id, "booking_ref": case.booking_ref},
    )
