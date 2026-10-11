"""Loop guard: three rules shared by both agent runtimes and the graph shim.

check_loop()     pure function, testable in isolation
loop_guard_node  graph node; reads `recent_tool_calls`, sets `loop_detected`

Rules:
  1. The same (tool, args) seen 3+ times in the last 5 calls
  2. Ping-pong A-B-A-B in the last 4 calls
  3. The same tool called 5+ times in a row
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)

MAX_LOOP_HISTORY = 5


def check_loop(recent_tool_calls: list[dict[str, Any]]) -> bool:
    if len(recent_tool_calls) < 3:
        return False

    pairs = [
        (tc["name"], json.dumps(tc.get("arguments", {}), sort_keys=True, default=str))
        for tc in recent_tool_calls[-MAX_LOOP_HISTORY:]
    ]
    if any(c >= 3 for c in Counter(pairs).values()):
        return True
    if len(pairs) >= 4:
        names = [p[0] for p in pairs[-4:]]
        if names[0] == names[2] and names[1] == names[3] and names[0] != names[1]:
            return True
    return len(pairs) >= 5 and len({p[0] for p in pairs[-5:]}) == 1


async def loop_guard_node(state: Any) -> dict[str, Any]:
    recent = state.get("recent_tool_calls") or []
    detected = check_loop(recent)
    if detected:
        logger.warning("Loop detected after %d tool calls", len(recent))
    return {"loop_detected": detected}
