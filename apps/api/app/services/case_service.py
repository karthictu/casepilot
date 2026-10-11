"""Case lifecycle: pull from the case source, process, persist, escalate. Shared by the REST router and Temporal."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.agents.case_processor import CaseInput, CaseProcessingResult, process_case
from app.integrations.case_source import get_case_source
from app.models import Case, HitlItem
from app.models import case as case_status
from app.models import hitl_item as hitl_status
from app.services import hitl
from app.services.errors import Conflict, NotFound

_NOT_REPROCESSABLE = {case_status.PROCESSING, case_status.BOOKED}


async def pull_cases(db: AsyncSession, *, actor: str, limit: int = 100) -> dict[str, int]:
    since = (await db.execute(select(func.max(Case.created_at)))).scalar()
    inbound = await get_case_source().fetch_new(since=since, limit=limit)
    existing = set(
        (
            await db.execute(select(Case.external_id).where(Case.external_id.in_([c.external_id for c in inbound])))
        ).scalars()
    )
    created = 0
    for c in inbound:
        if c.external_id in existing:
            continue
        db.add(
            Case(
                external_id=c.external_id,
                subject=c.subject,
                description=c.description,
                from_address=c.from_address,
                reason=c.reason,
                # The source's own timestamp, so the next pull's `since` cursor is in CRM time.
                **({"created_at": c.created_at} if c.created_at else {}),
            )
        )
        created += 1
    await audit.emit(
        db, "cases.pulled", actor=actor, surface="case_driven", payload={"pulled": len(inbound), "created": created}
    )
    await db.commit()
    return {"pulled": len(inbound), "created": created}


async def list_cases(db: AsyncSession, *, status: str | None = None, limit: int = 100) -> tuple[list[Case], int]:
    q = select(Case)
    count_q = select(func.count()).select_from(Case)
    if status:
        q, count_q = q.where(Case.status == status), count_q.where(Case.status == status)
    rows = list((await db.execute(q.order_by(Case.created_at.desc()).limit(limit))).scalars())
    return rows, (await db.execute(count_q)).scalar_one()


async def get_case(db: AsyncSession, case_id: str) -> Case:
    case = await db.get(Case, case_id)
    if case is None:
        raise NotFound(f"Case {case_id} not found")
    return case


async def ensure_processable(db: AsyncSession, case: Case) -> None:
    if case.status in _NOT_REPROCESSABLE:
        raise Conflict(f"Case {case.id} is {case.status}")
    if case.hitl_item_id:
        item = await db.get(HitlItem, case.hitl_item_id)
        if item is not None and item.status in (hitl_status.PENDING, hitl_status.APPROVED):
            raise Conflict(f"Case {case.id} already has an open HITL item")


async def process(
    db: AsyncSession, case_id: str, *, actor: str, workflow_id: str | None = None
) -> tuple[Case, CaseProcessingResult]:
    case = await get_case(db, case_id)
    await ensure_processable(db, case)
    case.status = case_status.PROCESSING
    await db.flush()

    result = await process_case(
        CaseInput(
            id=case.id,
            subject=case.subject,
            description=case.description,
            reason=case.reason,
            from_address=case.from_address,
        )
    )
    case.status = result.status
    # A skipped case was never extracted, so it has no intent or confidence.
    skipped = result.status == case_status.SKIPPED
    case.intent, case.confidence = (None, None) if skipped else (result.intent, result.confidence)
    case.booking_ref = result.booking_ref
    case.hitl_item_id = None

    if result.needs_hitl:
        proposal = result.proposed_call or {}
        item = await hitl.submit(
            db,
            source="case",
            source_ref=case.id,
            agent_id="booking",
            action=result.hitl_action or hitl_status.MANUAL_REVIEW,
            payload={
                "tool": proposal.get("tool"),
                "arguments": proposal.get("arguments"),
                "context": {"case_id": case.id, "subject": case.subject, "extraction": result.extraction},
            },
            confidence=result.confidence,
            reason=result.hitl_reason,
            customer_id=case.from_address or None,
            workflow_id=workflow_id,
            actor=actor,
        )
        case.hitl_item_id = item.id

    case.result = result.to_dict()
    await audit.emit(db, f"case.{result.status}", actor=actor, surface="case_driven", payload=_audit_payload(result))
    await db.commit()
    return case, result


def _audit_payload(result: CaseProcessingResult) -> dict[str, Any]:
    keys = (
        "case_id",
        "status",
        "intent",
        "reason",
        "confidence",
        "shadow",
        "booking_outcome",
        "booking_ref",
        "hitl_reason",
        "hitl_action",
    )
    data = result.to_dict()
    return {k: data[k] for k in keys}
