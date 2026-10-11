"""The native agent runtime: a small, dependency-free tool-calling loop.

Per turn: call the model with the agent's scoped tools → run any tool calls through the gate (write gating +
rate limiting) → loop-check → feed the results back. Stops on a final answer, a loop, the cost cap, or max turns.
Guardrails run on the way in (user content) and out (final answer).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.agents.graphs.loop_guard import check_loop
from app.agents.guardrails import check_input, check_output
from app.agents.llm import get_llm_client
from app.agents.runtime.gate import execute_gated
from app.agents.tools import ToolRegistry
from app.agents.types import AgentConfig, AgentResult, AgentStatus, OperationType, SessionContext, TokenBudget
from app.observability.tracer import get_tracer

logger = logging.getLogger(__name__)


def guard_inbound(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    """Redact PII in user turns; return (messages, blocked_reason)."""
    out = []
    for m in messages:
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            g = check_input(m["content"])
            if g.blocked:
                return messages, g.reason
            m = {**m, "content": g.text}
        out.append(m)
    return out, None


async def run_native(
    config: AgentConfig, messages: list[dict[str, Any]], ctx: SessionContext, budget: TokenBudget
) -> AgentResult:
    llm = get_llm_client()
    tracer = get_tracer()
    guarded, blocked = guard_inbound(messages)
    if blocked:
        return AgentResult(status=AgentStatus.BLOCKED, error=f"Input blocked by guardrail: {blocked}")

    convo: list[dict[str, Any]] = [{"role": "system", "content": config.system_prompt}, *guarded]
    op = OperationType.WRITE if ctx.write_allowed else OperationType.READ
    tools = ToolRegistry.to_openai_tools(ToolRegistry.get_scoped_tools(config.name, op)) or None
    result = AgentResult(status=AgentStatus.MAX_TURNS)
    recent: list[dict[str, Any]] = []

    def _finish(status: AgentStatus, *, output: str | None = None, error: str | None = None) -> AgentResult:
        result.status, result.output, result.error = status, output, error
        result.total_input_tokens, result.total_output_tokens = budget.input_tokens, budget.output_tokens
        result.total_cost_usd = budget.cost_usd
        return result

    for turn in range(1, config.max_turns + 1):
        result.turns = turn
        with tracer.span(f"llm:{config.name}", as_type="generation", input=convo[-1]) as gen:
            resp = await llm.complete(
                model=config.model, messages=convo, tools=tools, temperature=config.temperature, agent_name=config.name
            )
            gen.update(
                output=resp.content or [tc.name for tc in resp.tool_calls],
                model=resp.model or config.model,
                usage_details={"input": resp.input_tokens, "output": resp.output_tokens},
            )
        budget.add(resp.input_tokens, resp.output_tokens, resp.cost_usd)
        if budget.exceeded:
            return _finish(AgentStatus.COST_EXCEEDED, error=f"Cost budget exceeded: ${budget.cost_usd:.4f}")

        if not resp.tool_calls:
            g = check_output(resp.content or "")
            if g.blocked:
                return _finish(AgentStatus.BLOCKED, error=f"Output blocked by guardrail: {g.reason}")
            return _finish(AgentStatus.SUCCESS, output=g.text)

        convo.append(
            {
                "role": "assistant",
                "content": resp.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in resp.tool_calls
                ],
            }
        )
        for tc in resp.tool_calls:
            recent.append({"name": tc.name, "arguments": tc.arguments})
            if check_loop(recent):
                logger.warning("[%s] loop detected after %d tool calls", config.name, len(recent))
                return _finish(AgentStatus.LOOP_DETECTED, error="Agent loop detected")
            with tracer.span(f"tool:{tc.name}", as_type="tool", input=tc.arguments) as span:
                call = await execute_gated(
                    tc.name, tc.arguments, write_allowed=ctx.write_allowed, caller=ctx.customer_id, call_id=tc.id
                )
                span.update(output=call.result if call.error is None else {"error": call.error})
            result.tool_calls.append(call)
            content = call.result if call.error is None else {"error": call.error}
            convo.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(content, default=str)})

    return _finish(AgentStatus.MAX_TURNS, error=f"No final answer after {config.max_turns} turns")
