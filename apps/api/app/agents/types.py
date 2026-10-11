"""Core agent framework types."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class OperationType(StrEnum):
    READ = "read"
    WRITE = "write"


class AgentStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    MAX_TURNS = "max_turns"
    LOOP_DETECTED = "loop_detected"
    COST_EXCEEDED = "cost_exceeded"
    BLOCKED = "blocked"  # input or output failed a guardrail


@dataclass
class AgentConfig:
    name: str
    model: str
    system_prompt: str
    max_turns: int = 6
    temperature: float = 0.0


@dataclass
class SessionContext:
    """Per-run context the runtime seeds. The model can read it but never change it."""

    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    customer_id: str | None = None
    # True only when the caller has been granted write permission (operator approval, or live mode above threshold).
    write_allowed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
            "result": self.result,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 1),
        }


@dataclass
class TokenBudget:
    max_cost_usd: float = 0.0  # 0 = no cap
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def add(self, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += cost_usd

    @property
    def exceeded(self) -> bool:
        return bool(self.max_cost_usd) and self.cost_usd >= self.max_cost_usd


@dataclass
class AgentResult:
    status: AgentStatus
    output: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    turns: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    error: str | None = None

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "turns": self.turns,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": self.total_cost_usd,
            "error": self.error,
        }


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD estimate from LiteLLM's model price map when it is installed; 0.0 otherwise (e.g. the mock LLM)."""
    try:
        import litellm

        prompt_cost, completion_cost = litellm.cost_per_token(
            model=model, prompt_tokens=input_tokens, completion_tokens=output_tokens
        )
        return float(prompt_cost + completion_cost)
    except Exception:
        return 0.0
