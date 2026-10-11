"""`run_agent`: the one entry point every agent calls. Dispatches to the configured runtime.

- `native` (default): the owned tool loop in `native.py`, no extra dependencies.
- `adk`: Google ADK (`LlmAgent` + `InMemoryRunner`) in `adk_engine.py`, with the same gating, loop and cost rules.

Both return the same `AgentResult`, so agents never know which runtime ran them.
"""

from __future__ import annotations

from typing import Any

from app.agents.types import AgentConfig, AgentResult, SessionContext, TokenBudget
from app.config import settings
from app.observability.tracer import get_tracer


async def run_agent(
    config: AgentConfig,
    messages: list[dict[str, Any]],
    ctx: SessionContext | None = None,
    budget: TokenBudget | None = None,
) -> AgentResult:
    ctx = ctx or SessionContext()
    budget = budget or TokenBudget(max_cost_usd=settings.max_cost_usd_per_run)
    with get_tracer().span(
        f"agent:{config.name}",
        as_type="agent",
        input=messages[-1] if messages else None,
        metadata={"runtime": settings.agent_runtime, "model": config.model, "write_allowed": ctx.write_allowed},
    ) as span:
        if settings.agent_runtime == "adk":
            from app.agents.runtime.adk_engine import run_adk

            result = await run_adk(config, messages, ctx, budget)
        else:
            from app.agents.runtime.native import run_native

            result = await run_native(config, messages, ctx, budget)
        span.update(output=result.output, metadata=result.diagnostics())
    return result
