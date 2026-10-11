"""Case processor: the primary, case-driven ingress. Inbound case → outcome, deterministically routed.

    1. Pre-router: only cases whose CRM reason is in `owned_reasons` are processed; others are SKIPPED and left
       to the team that owns them.
    2. Extract: the extraction agent turns subject + body into a structured booking request.
    2b. Cross-check: the extracted intent must match what the CRM reason implies, or the case goes to an operator.
    3. Gate: confidence ≥ threshold, nothing missing, and `write_mode=live` → the booking agent may write.
       Otherwise it runs read-only and proposes the write.
    4. Book: the booking agent (reused, not duplicated) executes or proposes.

No LLM routing hop: the case carries its own reason and the extractor yields the intent. This module is pure,
with no DB writes; `services/case_service.py` persists the result, opens HITL items and writes the audit trail.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.agents.booking import AGENT_ID as BOOKING_AGENT
from app.agents.booking import run_booking_agent
from app.agents.extraction import extract_booking_request
from app.agents.plugin import load_plugins, registry
from app.config import settings
from app.models import case as case_status
from app.models.hitl_item import MANUAL_REVIEW

# The intent each owned CRM reason should extract to. A mismatch (e.g. an "amend" case that reads as a cancel) is
# escalated rather than acted on. Reasons without an entry here skip the check.
REASON_INTENTS: dict[str, str] = {
    "booking_create": "create_booking",
    "booking_amend": "amend_booking",
    "booking_cancel": "cancel_booking",
}


@dataclass
class CaseInput:
    id: str
    subject: str
    description: str
    reason: str
    from_address: str = ""


@dataclass
class CaseProcessingResult:
    case_id: str
    status: str
    intent: str = "unknown"
    reason: str = ""
    confidence: float = 0.0
    needs_hitl: bool = False
    hitl_reason: str = ""
    hitl_action: str | None = None  # tool name to approve, or "manual_review"
    proposed_call: dict[str, Any] | None = None
    booking_ref: str | None = None
    booking_outcome: str | None = None
    shadow: bool = True
    extraction: dict[str, Any] = field(default_factory=dict)
    decision: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _hitl(result: CaseProcessingResult, reason: str, proposed_call: dict[str, Any] | None) -> CaseProcessingResult:
    result.status = case_status.HITL_REQUIRED
    result.needs_hitl = True
    result.hitl_reason = reason
    result.proposed_call = proposed_call
    result.hitl_action = proposed_call["tool"] if proposed_call else MANUAL_REVIEW
    return result


async def process_case(case: CaseInput, *, write_mode: str | None = None) -> CaseProcessingResult:
    load_plugins()
    write_mode = write_mode or settings.write_mode
    threshold = settings.hitl_confidence_threshold
    result = CaseProcessingResult(case_id=case.id, status=case_status.PROCESSING, reason=case.reason)

    # 1. Pre-router
    if case.reason not in settings.owned_reasons:
        result.status = case_status.SKIPPED
        result.hitl_reason = f"Reason '{case.reason}' is not owned by this platform"
        return result

    # 2. Extract
    extraction, _ = await extract_booking_request(case.subject, case.description, customer_id=case.from_address)
    result.intent, result.confidence = extraction.intent, extraction.confidence
    result.extraction = extraction.model_dump()

    expected = REASON_INTENTS.get(case.reason)
    if expected and extraction.intent != expected:
        return _hitl(result, f"Case reason '{case.reason}' but the request reads as '{extraction.intent}'", None)

    booking = registry.get(BOOKING_AGENT)
    if booking is None or extraction.intent not in booking.intents:
        return _hitl(result, f"Intent '{extraction.intent}' is not something the booking agent can act on", None)

    # 3. Gate
    confident = extraction.confidence >= threshold and not extraction.missing_fields
    write_allowed = write_mode == "live" and confident
    result.shadow = not write_allowed

    # 4. Book
    decision, _ = await run_booking_agent(
        f"{case.subject}\n\n{case.description}",
        structured_request=extraction.booking_fields(),
        write_allowed=write_allowed,
        customer_id=case.from_address or None,
    )
    result.decision = decision
    result.booking_outcome = decision.get("outcome")
    result.booking_ref = decision.get("booking_ref") or extraction.booking_ref

    if decision["outcome"] == "executed":
        result.status = case_status.BOOKED
        return result
    if decision["outcome"] == "failed" and not decision.get("proposed_call"):
        result.status = case_status.FAILED
        result.hitl_reason = decision.get("reasoning", "")
        return result

    if not confident:
        missing = f"; missing: {', '.join(extraction.missing_fields)}" if extraction.missing_fields else ""
        reason = f"Extraction confidence {extraction.confidence:.2f} below threshold {threshold}{missing}"
    elif write_mode == "shadow":
        reason = "Shadow mode: writes need operator approval"
    else:
        reason = decision.get("reasoning") or "Booking agent escalated"
    return _hitl(result, reason, decision.get("proposed_call"))
