"""Temporal activities: thin wrappers over the case and HITL services, each in its own DB session."""

from __future__ import annotations

from dataclasses import dataclass

from temporalio import activity

from app.database import session_scope
from app.services import case_service, hitl


@dataclass
class ProcessCaseInput:
    case_id: str
    workflow_id: str
    actor: str = "temporal"


@dataclass
class ProcessCaseOutput:
    status: str
    hitl_item_id: str | None


@dataclass
class FinalizeOutput:
    hitl_status: str
    case_status: str | None


@activity.defn
async def process_case_activity(inp: ProcessCaseInput) -> ProcessCaseOutput:
    async with session_scope() as db:
        # Idempotent under retry: if an earlier attempt already committed for this workflow, return its outcome.
        case = await case_service.get_case(db, inp.case_id)
        if case.hitl_item_id:
            item = await hitl.get(db, case.hitl_item_id)
            if item.workflow_id == inp.workflow_id:
                return ProcessCaseOutput(status=case.status, hitl_item_id=item.id)
        case, result = await case_service.process(db, inp.case_id, actor=inp.actor, workflow_id=inp.workflow_id)
        return ProcessCaseOutput(status=result.status, hitl_item_id=case.hitl_item_id)


@activity.defn
async def finalize_review_activity(item_id: str) -> FinalizeOutput:
    """Execute an approved item (or apply a rejection) exactly once; a retry after success is a no-op."""
    async with session_scope() as db:
        item = await hitl.get(db, item_id)
        if item.status in ("approved", "rejected"):
            await hitl.finalize(db, item)
            await db.commit()
        case = await case_service.get_case(db, item.source_ref) if item.source == "case" else None
        return FinalizeOutput(hitl_status=item.status, case_status=case.status if case else None)
