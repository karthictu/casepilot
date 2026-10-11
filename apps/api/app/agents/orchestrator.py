"""Orchestrator: classifies a free-text request into one intent and routes it to the agent that owns it.

Read-only and tool-less. The intent list is built from the plugin registry at call time, and `route_to` is
looked up from the registry's routing table in code, so the model chooses an intent but never a destination.
"""

from __future__ import annotations

from typing import Any

from app.agents._json import coerce_to_dict
from app.agents.plugin import registry
from app.agents.runtime.engine import run_agent
from app.agents.types import AgentConfig, SessionContext
from app.config import settings

AGENT_NAME = "orchestrator"
UNKNOWN = "unknown"

_PROMPT = """You are the routing orchestrator for a logistics customer-service platform.
Classify the customer's latest request into exactly one intent.

Intents:
{intents}
- unknown: anything else, or a request you cannot classify confidently

{memory}
Return exactly one JSON object and nothing else:
{{"intent": "<one intent from the list>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}}"""


def build_prompt(memory_block: str = "") -> str:
    lines = []
    for plugin in registry.list():
        for intent in plugin.intents:
            lines.append(f"- {intent}: handled by {plugin.display_name}. {plugin.description}")
    return _PROMPT.format(intents="\n".join(lines), memory=memory_block)


async def run_orchestrator(
    query: str,
    *,
    customer_id: str | None = None,
    history: list[dict[str, str]] | None = None,
    memory_block: str = "",
    model: str | None = None,
) -> dict[str, Any]:
    config = AgentConfig(
        name=AGENT_NAME, model=model or settings.model_intent, system_prompt=build_prompt(memory_block)
    )
    messages = [*(history or []), {"role": "user", "content": query}]
    result = await run_agent(config, messages, SessionContext(customer_id=customer_id))
    raw = coerce_to_dict(result.output)

    table = registry.routing_table()
    intent = raw.get("intent") if raw.get("intent") in table else UNKNOWN
    try:
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "intent": intent,
        "confidence": confidence if intent != UNKNOWN else min(confidence, 0.5),
        "route_to": table.get(intent, "hitl"),
        "reasoning": raw.get("reasoning", result.error or ""),
        "_diagnostics": result.diagnostics(),
    }
