"""End-to-end CaseWorkflow on Temporal's time-skipping test server (downloaded on first run; skipped offline)."""

import uuid

import pytest

pytest.importorskip("temporalio")

from temporalio.testing import WorkflowEnvironment  # noqa: E402

from app.config import settings  # noqa: E402
from app.models import Case  # noqa: E402


@pytest.fixture
async def env():
    try:
        environment = await WorkflowEnvironment.start_time_skipping()
    except Exception as e:  # no network / unsupported platform
        pytest.skip(f"Temporal test server unavailable: {e}")
    async with environment:
        yield environment


async def test_case_workflow_waits_for_review_then_books(env, db, client, monkeypatch):
    from app.temporal import client as temporal_client
    from app.temporal.worker import build_worker
    from app.temporal.workflow import CaseWorkflow, CaseWorkflowInput

    monkeypatch.setattr(settings, "temporal_enabled", True)
    temporal_client.set_client(env.client)
    case = Case(
        external_id="T-1",
        subject="Book",
        description="Please book 2x40HC from Rotterdam to Singapore. Cargo ready date 2026-11-15.",
        reason="booking_create",
    )
    db.add(case)
    await db.commit()

    try:
        async with build_worker(env.client):
            handle = await env.client.start_workflow(
                CaseWorkflow.run,
                CaseWorkflowInput(case_id=case.id),
                id=f"case-{uuid.uuid4().hex}",
                task_queue=settings.temporal_task_queue,
            )
            for _ in range(50):
                if await handle.query(CaseWorkflow.phase) == "awaiting_review":
                    break
            item_id = (await client.get(f"/api/cases/{case.id}")).json()["hitl_item_id"]
            item = (await client.get(f"/api/hitl/queue/{item_id}")).json()
            assert item["workflow_id"] == handle.id

            reviewed = await client.post(f"/api/hitl/queue/{item_id}/review", json={"decision": "approve"})
            assert reviewed.json()["status"] == "approved"  # the workflow executes it

            result = await handle.result()
    finally:
        temporal_client.set_client(None)
    assert result.case_status == "booked" and result.hitl_status == "executed"
