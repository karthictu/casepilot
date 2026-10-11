"""Temporal client helpers. Works with a local dev server or Temporal Cloud (API key + TLS)."""

from __future__ import annotations

from temporalio.client import Client

from app.config import settings

_client: Client | None = None


async def connect() -> Client:
    kwargs: dict = {"namespace": settings.temporal_namespace}
    if settings.temporal_api_key:
        kwargs |= {"api_key": settings.temporal_api_key, "tls": True}
    elif settings.temporal_tls:
        kwargs["tls"] = True
    return await Client.connect(settings.temporal_address, **kwargs)


async def get_client() -> Client:
    global _client
    if _client is None:
        _client = await connect()
    return _client


def set_client(client: Client | None) -> None:
    global _client
    _client = client


def workflow_id_for(case_id: str) -> str:
    return f"case-{case_id}"


async def start_case_workflow(case_id: str, *, actor: str) -> str:
    from app.temporal.workflow import CaseWorkflow, CaseWorkflowInput

    client = await get_client()
    handle = await client.start_workflow(
        CaseWorkflow.run,
        CaseWorkflowInput(case_id=case_id, actor=actor),
        id=workflow_id_for(case_id),
        task_queue=settings.temporal_task_queue,
    )
    return handle.id


async def signal_review(workflow_id: str, item_id: str) -> None:
    client = await get_client()
    await client.get_workflow_handle(workflow_id).signal("review_submitted", item_id)
