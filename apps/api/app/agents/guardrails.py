"""Provider-agnostic guardrails: PII redaction and denied-topic blocking on agent input and output.

Regex-based on purpose: it runs the same whichever LLM provider is configured. A managed guardrail service
(e.g. a cloud provider's content filter) can be layered on top in the LLM client.

- PII (email, international phone numbers, card numbers that pass a Luhn check, IBANs) is **redacted**, not
  blocked: customers legitimately quote their own contact details.
- A denied topic **blocks** the run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# International format only (+CC ...) so dates, booking refs and quantities never look like phone numbers.
_PHONE_RE = re.compile(r"(?<![\w+])\+\d{1,3}[\s.-]?\(?\d{1,4}\)?(?:[\s.-]?\d{2,4}){2,4}(?!\w)")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")

DEFAULT_DENIED_TOPICS: tuple[str, ...] = ("weapons smuggling", "sanctions evasion", "bypass customs")


class GuardrailViolation(Exception):
    def __init__(self, reason: str, *, category: str):
        super().__init__(reason)
        self.category = category


@dataclass
class GuardrailResult:
    text: str
    redactions: list[str] = field(default_factory=list)
    blocked: bool = False
    reason: str | None = None


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def redact_pii(text: str) -> tuple[str, list[str]]:
    found: list[str] = []

    def sub(pattern: re.Pattern, label: str, s: str, check=None) -> str:
        def _r(m: re.Match) -> str:
            if check and not check(m.group(0)):
                return m.group(0)
            found.append(label)
            return f"[redacted-{label}]"

        return pattern.sub(_r, s)

    text = sub(_EMAIL_RE, "email", text)
    text = sub(_CARD_RE, "card", text, check=lambda s: _luhn_ok(re.sub(r"\D", "", s)))
    text = sub(_IBAN_RE, "iban", text)
    text = sub(_PHONE_RE, "phone", text)
    return text, found


def redact_value(value: Any, depth: int = 0) -> Any:
    """Redact PII in every string inside a JSON-like value."""
    if depth > 20:
        return value
    if isinstance(value, str):
        return redact_pii(value)[0]
    if isinstance(value, dict):
        return {k: redact_value(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(v, depth + 1) for v in value]
    return value


def _denied(text: str, topics: tuple[str, ...]) -> str | None:
    lowered = text.lower()
    return next((t for t in topics if t in lowered), None)


def check_input(text: str, *, denied_topics: tuple[str, ...] = DEFAULT_DENIED_TOPICS) -> GuardrailResult:
    topic = _denied(text, denied_topics)
    if topic:
        return GuardrailResult(text=text, blocked=True, reason=f"denied topic: {topic}")
    redacted, found = redact_pii(text)
    return GuardrailResult(text=redacted, redactions=found)


def check_output(text: str, *, denied_topics: tuple[str, ...] = DEFAULT_DENIED_TOPICS) -> GuardrailResult:
    return check_input(text, denied_topics=denied_topics)
