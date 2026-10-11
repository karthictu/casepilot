"""Tool registry: `@tool` decorator, JSON-schema derivation and scoped tool resolution.

The registry is the single source of truth for tool definitions, READ/WRITE classification, which agents may use
a tool (`agent_scopes`), and the OAuth scope an external caller needs to call it over MCP (`scope`). Every
execution path (the native runtime, the ADK runtime, MCP, HITL approval) goes through `runtime/gate.py`, which
applies write gating and rate limiting on top of `ToolRegistry.execute`.
"""

from __future__ import annotations

import inspect
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, get_type_hints

from app.agents.types import OperationType, ToolCall

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    name: str
    description: str
    func: Callable[..., Any] | Callable[..., Awaitable[Any]]
    parameters: dict[str, Any]
    operation_type: OperationType
    agent_scopes: list[str]
    scope: str | None
    is_async: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "operation_type": self.operation_type.value,
            "agent_scopes": self.agent_scopes,
            "scope": self.scope,
            "parameters": self.parameters,
        }


_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _json_type(hint: Any) -> str:
    origin = getattr(hint, "__origin__", None)
    if origin is list:
        return "array"
    if origin is dict:
        return "object"
    args = [a for a in getattr(hint, "__args__", ()) if a is not type(None)]
    if args and hint not in _TYPE_MAP:  # Optional[X] / X | None
        return _json_type(args[0])
    return _TYPE_MAP.get(hint, "string")


def _build_schema(func: Callable) -> dict[str, Any]:
    """JSON Schema `parameters` object derived from the function signature."""
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        if name in ("self", "ctx", "context", "session"):
            continue
        properties[name] = {"type": _json_type(hints.get(name, str))}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


class ToolRegistry:
    _tools: dict[str, ToolDefinition] = {}

    @classmethod
    def register(
        cls,
        name: str | None = None,
        description: str = "",
        operation_type: OperationType = OperationType.READ,
        agent_scopes: list[str] | None = None,
        scope: str | None = None,
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            cls._tools[tool_name] = ToolDefinition(
                name=tool_name,
                description=description or inspect.getdoc(func) or "",
                func=func,
                parameters=_build_schema(func),
                operation_type=operation_type,
                agent_scopes=agent_scopes or [],
                scope=scope,
                is_async=inspect.iscoroutinefunction(func),
            )
            logger.debug("Registered tool %s (agents=%s, type=%s)", tool_name, agent_scopes, operation_type)
            return func

        return decorator

    @classmethod
    def get(cls, name: str) -> ToolDefinition | None:
        return cls._tools.get(name)

    @classmethod
    def all(cls) -> list[ToolDefinition]:
        return list(cls._tools.values())

    @classmethod
    def get_scoped_tools(
        cls, agent_name: str, operation_type: OperationType = OperationType.READ
    ) -> list[ToolDefinition]:
        """Tools an agent may be offered. READ sessions get read tools only; WRITE sessions get both."""
        result = []
        for td in cls._tools.values():
            if td.agent_scopes and agent_name not in td.agent_scopes:
                continue
            if td.operation_type == OperationType.WRITE and operation_type == OperationType.READ:
                continue
            result.append(td)
        return result

    @classmethod
    def write_tools_for(cls, agent_name: str) -> list[ToolDefinition]:
        return [
            td
            for td in cls._tools.values()
            if td.operation_type == OperationType.WRITE and (not td.agent_scopes or agent_name in td.agent_scopes)
        ]

    @staticmethod
    def to_openai_tools(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in tools
        ]

    @classmethod
    async def execute(cls, name: str, arguments: dict[str, Any]) -> ToolCall:
        """Run a tool with no gating. Callers go through `runtime.gate.execute_gated` instead."""
        tool_def = cls._tools.get(name)
        if not tool_def:
            return ToolCall(name=name, arguments=arguments, error=f"Unknown tool: {name}")
        # Framework-injected keys (e.g. `_call_id`) never reach the tool function.
        invoke_args = {k: v for k, v in arguments.items() if not k.startswith("_")}
        start = time.monotonic()
        try:
            result = await tool_def.func(**invoke_args) if tool_def.is_async else tool_def.func(**invoke_args)
            return ToolCall(
                name=name, arguments=arguments, result=result, duration_ms=(time.monotonic() - start) * 1000
            )
        except Exception as e:
            logger.warning("Tool %s failed: %s", name, e)
            return ToolCall(name=name, arguments=arguments, error=str(e), duration_ms=(time.monotonic() - start) * 1000)


def tool(
    name: str | None = None,
    description: str = "",
    operation_type: OperationType = OperationType.READ,
    agent_scopes: list[str] | None = None,
    scope: str | None = None,
) -> Callable:
    """Decorator that registers a function as an agent tool."""
    return ToolRegistry.register(
        name=name, description=description, operation_type=operation_type, agent_scopes=agent_scopes, scope=scope
    )
