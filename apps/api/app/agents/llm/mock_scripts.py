"""Built-in mock scripts for the bundled agents (orchestrator, extraction, booking, tracking).

Keyword- and regex-driven stand-ins for a real model. They are deliberately simple and deterministic: good enough
to drive every branch of the flow (routing, HITL escalation, write proposals, tool use) in tests, evals and demos.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.agents.graphs.state import STRUCTURED_MARKER
from app.agents.llm.base import LLMResponse, LLMToolCall
from app.agents.llm.mock import mock_script

# Earlier entries win when several match; more than one match lowers confidence (ambiguous request).
_INTENT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("cancel_booking", re.compile(r"\bcancel", re.I)),
    ("amend_booking", re.compile(r"\b(amend|change|modify)\b", re.I)),
    ("get_booking_status", re.compile(r"\b(booking status|status of (my |the )?booking|booking confirmed)\b", re.I)),
    ("track_shipment", re.compile(r"\b(where is|track|tracking|eta|arriv\w*|milestones?)\b", re.I)),
    ("create_booking", re.compile(r"\b(book|new booking|booking request|reserve|need space)\b", re.I)),
]

_REF_RE = re.compile(r"\b(BK-\d{6})\b", re.I)
_CONTAINER_RE = re.compile(
    r"\b(\d{1,3})\s*(?:x\s*)?(20|40|45)\s*(?:ft|'|foot)?\s*(HC|GP|DV|RF|high[- ]cube|dry|reefer)?\b", re.I
)
_ROUTE_STOP = r"(?=[,.;:?!\n]|\s+(?:on|by|with|cargo|ready|for|departing|next|this|in|before|after|asap)\b|$)"
_ROUTE_RE = re.compile(rf"\bfrom\s+([A-Z][\w .-]*?)\s+to\s+([A-Z][\w .-]*?){_ROUTE_STOP}")
_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_COMMODITY_RE = re.compile(r"\bcommodity\s*[:\-]?\s*([A-Za-z][\w ]*?)(?=[,.;\n]|$)", re.I)
_TYPE_ALIASES = {"high cube": "HC", "high-cube": "HC", "dry": "GP", "reefer": "RF", "dv": "GP"}


# ── helpers ──────────────────────────────────────────────────────────────────


def keyword_intent(text: str) -> tuple[str, float]:
    matched = [intent for intent, pattern in _INTENT_PATTERNS if pattern.search(text)]
    if not matched:
        return "unknown", 0.3
    return matched[0], 0.93 if len(matched) == 1 else 0.6


def extract_fields(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if m := _REF_RE.search(text):
        fields["booking_ref"] = m.group(1).upper()
    if m := _CONTAINER_RE.search(text):
        kind = (m.group(3) or "GP").lower()
        fields["container_count"] = int(m.group(1))
        fields["container_type"] = f"{m.group(2)}{_TYPE_ALIASES.get(kind, kind.upper())}"
    if m := _ROUTE_RE.search(text):
        fields["origin"], fields["destination"] = m.group(1).strip(), m.group(2).strip()
    if m := _DATE_RE.search(text):
        fields["cargo_ready_date"] = m.group(1)
    if m := _COMMODITY_RE.search(text):
        fields["commodity"] = m.group(1).strip()

    changes: dict[str, Any] = {}
    if m := re.search(r"\b(?:count|quantity|number of containers)\s+to\s+(\d+)", text, re.I):
        changes["container_count"] = int(m.group(1))
    if m := re.search(r"\bdestination\s+to\s+([A-Z][\w .-]*?)(?=[,.;\n]|$)", text):
        changes["destination"] = m.group(1).strip()
    if m := re.search(r"\b(?:ready date|cargo ready date)\s+to\s+(20\d{2}-\d{2}-\d{2})", text, re.I):
        changes["cargo_ready_date"] = m.group(1)
    if changes:
        fields["changes"] = changes
    return fields


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            content = m.get("content")
            return content if isinstance(content, str) else json.dumps(content)
    return ""


def _structured_request(text: str) -> dict[str, Any] | None:
    if STRUCTURED_MARKER not in text:
        return None
    try:
        return json.loads(text.split(STRUCTURED_MARKER, 1)[1].strip())
    except json.JSONDecodeError:
        return None


def _tool_results(messages: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """[(tool name, parsed result)] in call order."""
    names: dict[str, str] = {}
    results: list[tuple[str, dict[str, Any]]] = []
    for m in messages:
        for tc in m.get("tool_calls") or []:
            names[tc["id"]] = tc["function"]["name"]
        if m.get("role") == "tool":
            try:
                parsed = json.loads(m.get("content") or "{}")
            except json.JSONDecodeError:
                parsed = {"raw": m.get("content")}
            results.append((names.get(m.get("tool_call_id", ""), "?"), parsed if isinstance(parsed, dict) else {}))
    return results


def _offered(tools: list[dict[str, Any]], name: str) -> bool:
    return any(t["function"]["name"] == name for t in tools)


def _call(name: str, arguments: dict[str, Any]) -> LLMResponse:
    return LLMResponse(tool_calls=[LLMToolCall(id=f"call_{uuid.uuid4().hex[:8]}", name=name, arguments=arguments)])


def _final(payload: dict[str, Any]) -> LLMResponse:
    return LLMResponse(content=json.dumps(payload))


# ── scripts ──────────────────────────────────────────────────────────────────


@mock_script("orchestrator")
def orchestrator(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
    intent, confidence = keyword_intent(_last_user_text(messages))
    return _final({"intent": intent, "confidence": confidence, "reasoning": f"keyword match → {intent}"})


@mock_script("extraction")
def extraction(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
    text = _last_user_text(messages)
    intent, confidence = keyword_intent(text)
    return _final({"intent": intent, "confidence": confidence, **extract_fields(text)})


_ACTION_FOR_INTENT = {
    "create_booking": "booking_create",
    "amend_booking": "booking_amend",
    "cancel_booking": "booking_cancel",
    "get_booking_status": "booking_status",
}
_CREATE_FIELDS = ("origin", "destination", "container_type", "container_count", "cargo_ready_date")


def _booking_arguments(action: str, req: dict[str, Any]) -> dict[str, Any] | None:
    if action == "booking_create":
        if not all(req.get(f) for f in _CREATE_FIELDS):
            return None
        args = {f: req[f] for f in _CREATE_FIELDS}
        args["commodity"] = req.get("commodity") or "general cargo"
        return args
    if not req.get("booking_ref"):
        return None
    if action == "booking_amend":
        return {"booking_ref": req["booking_ref"], "changes": req.get("changes") or {}} if req.get("changes") else None
    if action == "booking_cancel":
        return {"booking_ref": req["booking_ref"], "reason": "customer request"}
    return {"booking_ref": req["booking_ref"]}


@mock_script("booking")
def booking(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
    text = _last_user_text(messages)
    req = _structured_request(text) or {**extract_fields(text), "intent": keyword_intent(text)[0]}
    action = _ACTION_FOR_INTENT.get(req.get("intent", ""), "none")
    confidence = float(req.get("confidence") or 0.9)
    args = _booking_arguments(action, req) if action != "none" else None
    results = _tool_results(messages)

    if results:  # second turn: report on what the tool did
        name, result = results[-1]
        if "error" in result:
            if "write gating" in str(result["error"]):
                return _final(
                    {
                        "action": action,
                        "outcome": "hitl_required",
                        "confidence": confidence,
                        "proposed_call": {"tool": name, "arguments": args},
                        "booking_ref": req.get("booking_ref"),
                        "reasoning": "Write not permitted in this session; proposing the call for operator approval.",
                    }
                )
            return _final(
                {
                    "action": action,
                    "outcome": "failed",
                    "confidence": confidence,
                    "reasoning": str(result["error"]),
                    "booking_ref": req.get("booking_ref"),
                }
            )
        if name == "booking_status":
            return _final(
                {
                    "action": action,
                    "outcome": "answered",
                    "confidence": confidence,
                    "booking_ref": result.get("booking_ref"),
                    "summary": f"Booking {result.get('booking_ref')} is {result.get('status')}.",
                }
            )
        return _final(
            {
                "action": action,
                "outcome": "executed",
                "confidence": confidence,
                "booking_ref": result.get("booking_ref"),
                "summary": f"{action} succeeded for {result.get('booking_ref')}.",
            }
        )

    if action == "none":
        return _final(
            {
                "action": "none",
                "outcome": "hitl_required",
                "confidence": 0.3,
                "reasoning": "Could not tell which booking action is wanted.",
            }
        )
    if args is None:
        return _final(
            {
                "action": action,
                "outcome": "hitl_required",
                "confidence": min(confidence, 0.6),
                "proposed_call": None,
                "booking_ref": req.get("booking_ref"),
                "reasoning": "Required details are missing; an operator must complete them.",
            }
        )
    if _offered(tools, action):
        return _call(action, args)
    return _final(
        {
            "action": action,
            "outcome": "hitl_required",
            "confidence": confidence,
            "proposed_call": {"tool": action, "arguments": args},
            "booking_ref": req.get("booking_ref"),
            "reasoning": "Write tool not available in this session; proposing the call for approval.",
        }
    )


@mock_script("tracking")
def tracking(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
    text = _last_user_text(messages)
    ref_match = _REF_RE.search(text)
    results = _tool_results(messages)
    if not ref_match:
        return _final(
            {
                "outcome": "hitl_required",
                "confidence": 0.4,
                "shipment_ref": None,
                "summary": "I need a shipment or booking reference (e.g. BK-100001) to look this up.",
            }
        )
    ref = ref_match.group(1).upper()
    if not results and _offered(tools, "tracking_get_milestones"):
        return _call("tracking_get_milestones", {"shipment_ref": ref})
    result = results[-1][1] if results else {}
    if "error" in result or not result.get("milestones"):
        return _final(
            {
                "outcome": "not_found",
                "confidence": 0.9,
                "shipment_ref": ref,
                "summary": f"No tracking data found for {ref}.",
            }
        )
    last = result["milestones"][-1]
    return _final(
        {
            "outcome": "answered",
            "confidence": 0.92,
            "shipment_ref": ref,
            "summary": f"{ref}: last event '{last['event']}' at {last['location']} on {last['timestamp'][:10]}. "
            f"ETA {result.get('eta', 'unknown')}.",
        }
    )
