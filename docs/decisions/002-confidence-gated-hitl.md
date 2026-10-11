# ADR-002: Confidence-gated HITL; approval executes the proposed call verbatim

- **Status:** Accepted
- **Date:** 2026-10-09
- **Related:** [ADR-003](003-shadow-first-write-gating.md), [ADR-004](004-durable-workflows-with-temporal.md)

## Context
Inbound cases are free-text emails. A model can extract a booking request from most of them, but not all, and a
model's self-reported confidence is not evidence of completeness: a fluent answer can still be missing the cargo
ready date. Operators need to step in exactly when the platform is unsure, and when they approve something,
the thing that runs must be the thing they saw. A design that re-runs the model after approval ("go ahead and
do it") lets the model reinterpret the request between review and execution.

## Decision
1. **One threshold.** `CASEPILOT_HITL_CONFIDENCE_THRESHOLD` (default `0.85`). Case processing, the pipeline
   (per plugin `hitl_confidence_threshold`) and the bundled agents escalate below it.
2. **Completeness is computed in code.** `extraction.finalize` derives `missing_fields` from
   `REQUIRED_FIELDS[intent]`, never from the model, and caps confidence at `INCOMPLETE_CONFIDENCE_CAP = 0.6` when
   anything is missing or the intent is `unknown`. The cap is below the threshold, so an incomplete extraction
   can never pass the gate.
3. **The model proposes, the platform executes.** In a read-only session the booking agent returns a
   `proposed_call = {"tool", "arguments"}`. `enforce_invariants` keeps it only if it names a real write tool, and
   overrules any "executed" claim not backed by a successful write tool call in the same run.
4. **A HITL item stores exactly what will run** (`hitl_items.payload.tool` / `.arguments`). Approval calls
   `execute_gated(tool, arguments, write_allowed=True)`. The model is not consulted again.
5. **Operators may correct, visibly.** `ReviewRequest.tool` / `.arguments` replace the payload on approval; the
   previous values are kept in `payload.original`, and the full payload is in the `hitl.approved` audit event.
   Items with no executable call are `manual_review`; approving one requires `tool` and `arguments` (else 422).
6. **An item is reviewed once.** Review of a non-`pending` item returns 409.

## Consequences
- What the operator approves is what executes, byte for byte, which makes the audit trail meaningful and
  approval safe to delegate.
- Every review is a labelled example (approved unchanged, corrected, rejected) for measuring readiness to go
  live ([ADR-003](003-shadow-first-write-gating.md)).
- A wrong proposal cannot be "fixed" by the model after review; the operator must correct the arguments or
  reject. That is deliberate.
- Requests with several actions (cancel one booking and create another) produce one proposal for the first
  action; the rest needs an operator. A multi-call payload would be a future ADR.
- The threshold is global; per-reason or per-agent thresholds would need a setting per plugin or reason.

## Alternatives considered
| Option | Why not |
|---|---|
| Trust the model's confidence and its `missing_fields` | A fluent but incomplete extraction would pass; completeness is checkable in code, so check it. |
| Re-run the agent with write permission after approval | The second run can differ from what was approved; it also costs a second model call. |
| Approve an intent ("cancel BK-100001") instead of a call | The operator would not see the exact arguments; translation back into a call reintroduces the model. |
| Per-field confidence | More signal, but more prompt surface and no clear gain for the bundled intents; can be layered later. |

## Implementation notes
- Threshold: `hitl_confidence_threshold` in `apps/api/app/config.py`; plugin field in `app/agents/plugin.py`.
- Completeness and cap: `apps/api/app/agents/extraction.py` (`REQUIRED_FIELDS`, `INCOMPLETE_CONFIDENCE_CAP`, `finalize`).
- Gate rule: `apps/api/app/agents/case_processor.py` (step 3).
- Invariants: `apps/api/app/agents/booking.py` (`enforce_invariants`).
- Queue: `apps/api/app/services/hitl.py` (`submit`, `review`, `finalize`); model `app/models/hitl_item.py`
  (`MANUAL_REVIEW`); route `app/routers/hitl.py` (`ReviewRequest`).
- Tests: `tests/test_case_processor.py`, `tests/test_api_cases_hitl.py`
  (`test_manual_review_needs_operator_supplied_call`, `test_reviewing_twice_conflicts`),
  `tests/test_pipeline.py::test_model_claiming_an_unexecuted_write_is_overruled`.
