"""Google ADK runtime (`CASEPILOT_AGENT_RUNTIME=adk`, extra: `adk`).

Same contract as the native runtime: `run_adk(...) -> AgentResult`. Each run builds a fresh `LlmAgent` on an
`InMemoryRunner` with an ephemeral session, so agents stay stateless.

- **Model seam**: `BridgeLlm` is an ADK `BaseLlm` that forwards to casepilot's `LLMClient`, so ADK runs on the
  mock LLM offline or on LiteLLM (any provider) in production, with cost captured per call.
- **Tools**: each registry tool is wrapped in `GatedFunctionTool`, which runs through `runtime/gate.py`. Write
  permission is read from session state seeded by the runtime, never from the model.
- **Callbacks**: loop detection (`before_tool` / `before_model`) and cost accounting (`after_model`), reusing
  `check_loop` so the rules stay single-sourced with the native runtime.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from app.agents.graphs.loop_guard import check_loop
from app.agents.guardrails import check_output
from app.agents.llm import get_llm_client
from app.agents.runtime.gate import execute_gated
from app.agents.runtime.native import guard_inbound
from app.agents.tools import ToolDefinition, ToolRegistry
from app.agents.types import (
    AgentConfig,
    AgentResult,
    AgentStatus,
    OperationType,
    SessionContext,
    TokenBudget,
    ToolCall,
)

logger = logging.getLogger(__name__)

APP_NAME = "casepilot"
STATE_CUSTOMER_ID = "cp:customer_id"
STATE_WRITE_ALLOWED = "cp:write_allowed"
STATE_RECENT_TOOL_CALLS = "cp:recent_tool_calls"
STATE_TOOL_CALLS = "cp:tool_calls"
STATE_LOOP_DETECTED = "cp:loop_detected"
STATE_INPUT_TOKENS = "cp:input_tokens"
STATE_OUTPUT_TOKENS = "cp:output_tokens"
STATE_COST_USD = "cp:cost_usd"
_MAX_RECENT = 10


# ── Model seam ──────────────────────────────────────────────────────────────


def _system_text(llm_request: LlmRequest) -> str:
    instruction = getattr(llm_request.config, "system_instruction", None) if llm_request.config else None
    if instruction is None:
        return ""
    if isinstance(instruction, str):
        return instruction
    parts = getattr(instruction, "parts", None) or []
    return "\n".join(p.text for p in parts if getattr(p, "text", None))


def _to_openai_messages(llm_request: LlmRequest) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if system := _system_text(llm_request):
        messages.append({"role": "system", "content": system})
    for content in llm_request.contents or []:
        texts, calls = [], []
        for part in content.parts or []:
            if part.function_response is not None:
                fr = part.function_response
                messages.append(
                    {"role": "tool", "tool_call_id": fr.id or fr.name, "content": json.dumps(fr.response, default=str)}
                )
            elif part.function_call is not None:
                fc = part.function_call
                calls.append(
                    {
                        "id": fc.id or fc.name,
                        "type": "function",
                        "function": {"name": fc.name, "arguments": json.dumps(fc.args or {})},
                    }
                )
            elif part.text:
                texts.append(part.text)
        role = "assistant" if content.role == "model" else "user"
        if calls:
            messages.append({"role": "assistant", "content": "\n".join(texts) or None, "tool_calls": calls})
        elif texts:
            messages.append({"role": role, "content": "\n".join(texts)})
    return messages


class BridgeLlm(BaseLlm):
    """ADK model that forwards to casepilot's configured `LLMClient` (mock or LiteLLM)."""

    agent_name: str = ""

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        tool_defs = [td for name in (llm_request.tools_dict or {}) if (td := ToolRegistry.get(name))]
        temperature = getattr(llm_request.config, "temperature", None) if llm_request.config else None
        resp = await get_llm_client().complete(
            model=self.model,
            messages=_to_openai_messages(llm_request),
            tools=ToolRegistry.to_openai_tools(tool_defs) or None,
            temperature=temperature or 0.0,
            agent_name=self.agent_name,
        )
        parts: list[types.Part] = []
        if resp.content:
            parts.append(types.Part(text=resp.content))
        for tc in resp.tool_calls:
            parts.append(types.Part(function_call=types.FunctionCall(id=tc.id, name=tc.name, args=tc.arguments)))
        yield LlmResponse(
            content=types.Content(role="model", parts=parts or [types.Part(text="")]),
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=resp.input_tokens,
                candidates_token_count=resp.output_tokens,
                total_token_count=resp.input_tokens + resp.output_tokens,
            ),
            custom_metadata={"cost_usd": resp.cost_usd},
            model_version=resp.model or self.model,
        )


# ── Tools ───────────────────────────────────────────────────────────────────


class GatedFunctionTool(FunctionTool):
    """An ADK FunctionTool whose execution goes through casepilot's gate (write gating + rate limiting)."""

    def __init__(self, tool_def: ToolDefinition) -> None:
        super().__init__(func=tool_def.func)
        self.name = tool_def.name  # pin the registry name so MCP/A2A contract names and rate-limit keys line up
        if tool_def.description:
            self.description = tool_def.description

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> Any:
        state = tool_context.state
        call = await execute_gated(
            self.name,
            args,
            write_allowed=bool(state.get(STATE_WRITE_ALLOWED, False)),
            caller=state.get(STATE_CUSTOMER_ID),
            call_id=getattr(tool_context, "function_call_id", "") or "",
        )
        state[STATE_TOOL_CALLS] = [*(state.get(STATE_TOOL_CALLS) or []), call.to_dict()]
        return call.result if call.error is None else {"error": call.error}


def build_tools(agent_name: str, *, write_allowed: bool) -> list[GatedFunctionTool]:
    op = OperationType.WRITE if write_allowed else OperationType.READ
    return [GatedFunctionTool(td) for td in ToolRegistry.get_scoped_tools(agent_name, op)]


# ── Callbacks ───────────────────────────────────────────────────────────────


def loop_guard_before_tool(*, tool: Any, args: dict[str, Any], tool_context: Any) -> dict | None:
    state = tool_context.state
    recent = [
        *(state.get(STATE_RECENT_TOOL_CALLS) or []),
        {"name": getattr(tool, "name", str(tool)), "arguments": args},
    ]
    state[STATE_RECENT_TOOL_CALLS] = recent[-_MAX_RECENT:]
    if check_loop(recent):
        state[STATE_LOOP_DETECTED] = True
        if (actions := getattr(tool_context, "actions", None)) is not None:
            actions.escalate = True
        return {"error": "Agent loop detected: repeated or cyclic tool calls. The run has been stopped."}
    return None


def loop_guard_before_model(*, callback_context: Any, llm_request: Any) -> LlmResponse | None:
    # LlmAgent does not end its own loop on a tool callback's escalate, so enforce it at the next model turn.
    if callback_context.state.get(STATE_LOOP_DETECTED):
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(text="Run stopped: loop detected.")]))
    return None


def cost_after_model(*, callback_context: Any, llm_response: Any) -> None:
    usage = getattr(llm_response, "usage_metadata", None)
    state = callback_context.state
    if usage:
        state[STATE_INPUT_TOKENS] = (state.get(STATE_INPUT_TOKENS) or 0) + (usage.prompt_token_count or 0)
        state[STATE_OUTPUT_TOKENS] = (state.get(STATE_OUTPUT_TOKENS) or 0) + (usage.candidates_token_count or 0)
    cost = (getattr(llm_response, "custom_metadata", None) or {}).get("cost_usd", 0.0)
    state[STATE_COST_USD] = (state.get(STATE_COST_USD) or 0.0) + float(cost or 0.0)
    return None


# ── Run ─────────────────────────────────────────────────────────────────────


def _to_content(message: dict[str, Any]) -> types.Content:
    role = "model" if message.get("role") == "assistant" else "user"
    return types.Content(role=role, parts=[types.Part(text=str(message.get("content") or ""))])


async def run_adk(
    config: AgentConfig, messages: list[dict[str, Any]], ctx: SessionContext, budget: TokenBudget
) -> AgentResult:
    guarded, blocked = guard_inbound(messages)
    if blocked:
        return AgentResult(status=AgentStatus.BLOCKED, error=f"Input blocked by guardrail: {blocked}")
    if not guarded:
        return AgentResult(status=AgentStatus.ERROR, error="No input message")

    prompt = config.system_prompt
    agent = LlmAgent(
        name=config.name,
        model=BridgeLlm(model=config.model, agent_name=config.name),
        # A callable instruction is used verbatim; a string would be treated as a template and break on JSON braces.
        instruction=lambda _ctx: prompt,
        tools=build_tools(config.name, write_allowed=ctx.write_allowed),
        before_tool_callback=loop_guard_before_tool,
        before_model_callback=loop_guard_before_model,
        after_model_callback=cost_after_model,
        generate_content_config=types.GenerateContentConfig(temperature=config.temperature),
    )
    runner = InMemoryRunner(agent=agent, app_name=APP_NAME)
    user_id = ctx.customer_id or "anonymous"
    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        state={STATE_CUSTOMER_ID: ctx.customer_id, STATE_WRITE_ALLOWED: ctx.write_allowed},
    )
    # Prior turns are folded into the new message so the model sees the conversation.
    *history, last = guarded
    prefix = "\n".join(f"{m['role']}: {m.get('content', '')}" for m in history)
    new_message = _to_content({"role": "user", "content": f"{prefix}\n\n{last.get('content', '')}".strip()})

    final_text: str | None = None
    error: str | None = None
    turns = 0
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=new_message,
            run_config=RunConfig(max_llm_calls=max(2, config.max_turns * 2)),
        ):
            if event.error_message:
                error = event.error_message
            if event.content and not event.partial and event.author == config.name:
                turns += 1
                for part in event.content.parts or []:
                    if part.text:
                        final_text = part.text
    except Exception as e:  # surface as an ERROR result, like the native runtime
        logger.exception("[%s] ADK run failed", config.name)
        return AgentResult(status=AgentStatus.ERROR, error=str(e))

    final = await runner.session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session.id)
    state = final.state if final else {}
    budget.add(
        state.get(STATE_INPUT_TOKENS) or 0, state.get(STATE_OUTPUT_TOKENS) or 0, state.get(STATE_COST_USD) or 0.0
    )
    result = AgentResult(
        status=AgentStatus.SUCCESS,
        output=final_text,
        tool_calls=[ToolCall(**tc) for tc in state.get(STATE_TOOL_CALLS) or []],
        turns=turns,
        total_input_tokens=budget.input_tokens,
        total_output_tokens=budget.output_tokens,
        total_cost_usd=budget.cost_usd,
    )
    if state.get(STATE_LOOP_DETECTED):
        result.status, result.error = AgentStatus.LOOP_DETECTED, "Agent loop detected"
    elif budget.exceeded:
        result.status, result.error = AgentStatus.COST_EXCEEDED, f"Cost budget exceeded: ${budget.cost_usd:.4f}"
    elif error and final_text is None:
        result.status, result.error = AgentStatus.ERROR, error
    elif final_text is not None:
        g = check_output(final_text)
        if g.blocked:
            result.status, result.error, result.output = AgentStatus.BLOCKED, f"Output blocked: {g.reason}", None
        else:
            result.output = g.text
    else:
        result.status, result.error = AgentStatus.ERROR, "No final answer"
    return result
