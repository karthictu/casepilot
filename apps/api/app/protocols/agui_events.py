"""AG-UI (https://docs.ag-ui.com) wire events: plain JSON objects with a `type` discriminator, sent as SSE."""

from __future__ import annotations

import json
import uuid
from typing import Any


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def run_started(thread_id: str, run_id: str) -> dict[str, Any]:
    return {"type": "RUN_STARTED", "threadId": thread_id, "runId": run_id}


def run_finished(thread_id: str, run_id: str, result: Any = None) -> dict[str, Any]:
    event: dict[str, Any] = {"type": "RUN_FINISHED", "threadId": thread_id, "runId": run_id}
    if result is not None:
        event["result"] = result
    return event


def run_error(message: str, code: str | None = None) -> dict[str, Any]:
    return {"type": "RUN_ERROR", "message": message, **({"code": code} if code else {})}


def step(name: str) -> list[dict[str, Any]]:
    return [{"type": "STEP_STARTED", "stepName": name}, {"type": "STEP_FINISHED", "stepName": name}]


def text_message(content: str, *, chunk_words: int = 6) -> list[dict[str, Any]]:
    """START → CONTENT (in word chunks, so the UI renders progressively) → END."""
    mid = _id("msg")
    words = content.split(" ")
    chunks = [" ".join(words[i : i + chunk_words]) for i in range(0, len(words), chunk_words)] or [""]
    deltas = [c if i == len(chunks) - 1 else c + " " for i, c in enumerate(chunks)]
    return [
        {"type": "TEXT_MESSAGE_START", "messageId": mid, "role": "assistant"},
        *({"type": "TEXT_MESSAGE_CONTENT", "messageId": mid, "delta": d} for d in deltas if d),
        {"type": "TEXT_MESSAGE_END", "messageId": mid},
    ]


def tool_call(name: str, args: dict[str, Any], result: Any, call_id: str | None = None) -> list[dict[str, Any]]:
    tcid = call_id or _id("tc")
    return [
        {"type": "TOOL_CALL_START", "toolCallId": tcid, "toolCallName": name},
        {"type": "TOOL_CALL_ARGS", "toolCallId": tcid, "delta": json.dumps(args, default=str)},
        {"type": "TOOL_CALL_END", "toolCallId": tcid},
        {
            "type": "TOOL_CALL_RESULT",
            "messageId": _id("msg"),
            "toolCallId": tcid,
            "content": json.dumps(result, default=str),
            "role": "tool",
        },
    ]


def custom(name: str, value: Any) -> dict[str, Any]:
    return {"type": "CUSTOM", "name": name, "value": value}


def encode_sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"
