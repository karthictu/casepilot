"""The single choke point every tool call passes through, whichever runtime or surface made it.

1. **Write gating**: a WRITE tool is refused unless the session holds write permission. Permission is seeded by
   the platform (operator approval, or live mode above the confidence threshold), never by the model.
2. **Rate limiting**: per (tool, caller) sliding window.
"""

from __future__ import annotations

from typing import Any

from app.agents.rate_limit import get_limiter
from app.agents.tools import ToolRegistry
from app.agents.types import OperationType, ToolCall

WRITE_BLOCKED = "Write operation blocked: write gating active"


async def execute_gated(
    name: str, arguments: dict[str, Any], *, write_allowed: bool, caller: str | None = None, call_id: str = ""
) -> ToolCall:
    tool_def = ToolRegistry.get(name)
    if tool_def is None:
        return ToolCall(name=name, arguments=arguments, error=f"Unknown tool: {name}", id=call_id)
    if tool_def.operation_type == OperationType.WRITE and not write_allowed:
        return ToolCall(name=name, arguments=arguments, error=WRITE_BLOCKED, id=call_id)
    rl = get_limiter().check(name, caller or "anonymous")
    if not rl.allowed:
        error = f"Rate limit exceeded for {name} (retry after {rl.retry_after_seconds:.1f}s)"
        return ToolCall(name=name, arguments=arguments, error=error, id=call_id)
    call = await ToolRegistry.execute(name, arguments)
    call.id = call_id
    return call
