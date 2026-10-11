"""LiteLLM adapter: one client for 100+ providers (OpenAI, AWS Bedrock, Azure OpenAI, Anthropic, Vertex,
Ollama, ...), selected by the model string (`bedrock/...`, `azure/...`, `ollama/...`).

Set `CASEPILOT_LITELLM_API_BASE` to send every call through a LiteLLM proxy instead (central keys, budgets and
logging); the model string is then the proxy's model alias.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.agents.llm.base import LLMResponse, LLMToolCall
from app.config import settings

logger = logging.getLogger(__name__)


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        logger.warning("Tool-call arguments were not valid JSON: %r", raw)
        return {}


class LiteLLMClient:
    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        agent_name: str = "",
    ) -> LLMResponse:
        import litellm

        kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
        if tools:
            kwargs["tools"] = tools
        if settings.litellm_api_base:
            kwargs["model"] = model if model.startswith("litellm_proxy/") else f"litellm_proxy/{model}"
            kwargs["api_base"] = settings.litellm_api_base
            kwargs["api_key"] = settings.litellm_api_key
        kwargs["metadata"] = {"agent": agent_name}

        resp = await litellm.acompletion(**kwargs)
        message = resp.choices[0].message
        tool_calls = [
            LLMToolCall(id=tc.id, name=tc.function.name, arguments=_parse_arguments(tc.function.arguments))
            for tc in (getattr(message, "tool_calls", None) or [])
        ]
        usage = getattr(resp, "usage", None)
        try:
            cost = float(litellm.completion_cost(completion_response=resp))
        except Exception:
            cost = 0.0
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            cost_usd=cost,
            model=getattr(resp, "model", model) or model,
        )
