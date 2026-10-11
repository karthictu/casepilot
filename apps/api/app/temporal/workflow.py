"""Durable case workflow: process → (wait for the operator's review) → execute exactly once.

    process_case_activity ──► HITL? ──no──► done
                                 │
                                yes: wait for the `review_submitted` signal (up to REVIEW_TIMEOUT)
                                 ▼
                        finalize_review_activity  (runs the approved call, updates the case)

The workflow survives API restarts and deploys while it waits days for an operator, and the write activity has
a bounded retry policy so an approved booking is applied once.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities import (
        FinalizeOutput,
        ProcessCaseInput,
        ProcessCaseOutput,
        finalize_review_activity,
        process_case_activity,
    )

REVIEW_TIMEOUT = timedelta(days=7)
_READ_RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=1), backoff_coefficient=2.0)
_WRITE_RETRY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    non_retryable_error_types=["NotFound", "Invalid"],
)


@dataclass
class CaseWorkflowInput:
    case_id: str
    actor: str = "temporal"


@dataclass
class CaseWorkflowResult:
    case_status: str | None
    hitl_item_id: str | None = None
    hitl_status: str | None = None


@workflow.defn(name="CaseWorkflow")
class CaseWorkflow:
    def __init__(self) -> None:
        self._phase = "processing"
        self._reviewed_item: str | None = None

    @workflow.signal(name="review_submitted")
    def review_submitted(self, item_id: str) -> None:
        self._reviewed_item = item_id

    @workflow.query(name="phase")
    def phase(self) -> str:
        return self._phase

    @workflow.run
    async def run(self, inp: CaseWorkflowInput) -> CaseWorkflowResult:
        processed: ProcessCaseOutput = await workflow.execute_activity(
            process_case_activity,
            ProcessCaseInput(case_id=inp.case_id, workflow_id=workflow.info().workflow_id, actor=inp.actor),
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_READ_RETRY,
        )
        if not processed.hitl_item_id:
            self._phase = "done"
            return CaseWorkflowResult(case_status=processed.status)

        self._phase = "awaiting_review"
        try:
            await workflow.wait_condition(lambda: self._reviewed_item is not None, timeout=REVIEW_TIMEOUT)
        except TimeoutError:
            self._phase = "review_timeout"
            return CaseWorkflowResult(
                case_status=processed.status, hitl_item_id=processed.hitl_item_id, hitl_status="pending"
            )

        self._phase = "executing"
        final: FinalizeOutput = await workflow.execute_activity(
            finalize_review_activity,
            processed.hitl_item_id,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_WRITE_RETRY,
        )
        self._phase = "done"
        return CaseWorkflowResult(
            case_status=final.case_status, hitl_item_id=processed.hitl_item_id, hitl_status=final.hitl_status
        )
