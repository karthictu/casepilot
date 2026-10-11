"""Temporal worker entry point: `uv run python -m app.temporal.worker`."""

from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from app.agents.plugin import load_plugins
from app.config import settings
from app.temporal.activities import finalize_review_activity, process_case_activity
from app.temporal.client import connect
from app.temporal.workflow import CaseWorkflow


def build_worker(client) -> Worker:
    return Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[CaseWorkflow],
        activities=[process_case_activity, finalize_review_activity],
    )


async def main() -> None:
    logging.basicConfig(level=settings.log_level)
    load_plugins()
    client = await connect()
    logging.getLogger(__name__).info("Worker polling task queue '%s'", settings.temporal_task_queue)
    await build_worker(client).run()


if __name__ == "__main__":
    asyncio.run(main())
