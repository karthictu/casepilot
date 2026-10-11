"""Entity extraction: turns an inbound case (subject + body) into a structured booking request.

The model proposes fields; the code decides completeness. `missing_fields` is computed here from the intent's
required fields, and confidence is capped when anything required is missing, so a fluent but incomplete
extraction can never clear the HITL threshold.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.agents._json import coerce_to_dict
from app.agents.runtime.engine import run_agent
from app.agents.types import AgentConfig, SessionContext
from app.config import settings

AGENT_NAME = "extraction"

INTENTS = ("create_booking", "amend_booking", "cancel_booking", "get_booking_status", "track_shipment", "unknown")
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "create_booking": ("origin", "destination", "container_type", "container_count", "cargo_ready_date"),
    "amend_booking": ("booking_ref", "changes"),
    "cancel_booking": ("booking_ref",),
    "get_booking_status": ("booking_ref",),
    "track_shipment": ("booking_ref",),
}
INCOMPLETE_CONFIDENCE_CAP = 0.6


class BookingExtraction(BaseModel):
    intent: str = "unknown"
    booking_ref: str | None = None
    origin: str | None = None
    destination: str | None = None
    container_type: str | None = None
    container_count: int | None = None
    cargo_ready_date: str | None = None
    commodity: str | None = None
    changes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    missing_fields: list[str] = Field(default_factory=list)

    def booking_fields(self) -> dict[str, Any]:
        return self.model_dump(exclude={"missing_fields"}, exclude_none=True)


SYSTEM_PROMPT = f"""You extract structured booking requests from customer emails for a container shipping desk.
Return exactly one JSON object and nothing else, with these keys (omit unknown values; never invent them):
intent (one of {", ".join(INTENTS)}), booking_ref, origin, destination, container_type (e.g. 20GP, 40HC),
container_count (integer), cargo_ready_date (YYYY-MM-DD), commodity,
changes (object of field → new value, for amendments only), confidence (0.0-1.0)."""


def finalize(raw: dict[str, Any]) -> BookingExtraction:
    try:
        extraction = BookingExtraction.model_validate(raw)
    except ValidationError:
        extraction = BookingExtraction(intent=str(raw.get("intent", "unknown")))
    if extraction.intent not in INTENTS:
        extraction.intent = "unknown"
    required = REQUIRED_FIELDS.get(extraction.intent, ())
    extraction.missing_fields = [f for f in required if not getattr(extraction, f)]
    extraction.confidence = max(0.0, min(1.0, extraction.confidence))
    if extraction.missing_fields or extraction.intent == "unknown":
        extraction.confidence = min(extraction.confidence, INCOMPLETE_CONFIDENCE_CAP)
    return extraction


async def extract_booking_request(
    subject: str, body: str, *, customer_id: str | None = None
) -> tuple[BookingExtraction, dict[str, Any]]:
    config = AgentConfig(name=AGENT_NAME, model=settings.model_extraction, system_prompt=SYSTEM_PROMPT, max_turns=1)
    result = await run_agent(
        config, [{"role": "user", "content": f"Subject: {subject}\n\n{body}"}], SessionContext(customer_id=customer_id)
    )
    return finalize(coerce_to_dict(result.output)), result.diagnostics()
