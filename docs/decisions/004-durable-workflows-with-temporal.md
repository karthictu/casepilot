# ADR-004: Optional durable case workflows with Temporal

- **Status:** Accepted
- **Date:** 2026-10-09
- **Related:** [ADR-002](002-confidence-gated-hitl.md), [ADR-005](005-adapter-interfaces-for-integrations.md)

## Context
A case can wait days for an operator. Without a durable runtime, the waiting state lives only in the database
and the approved write runs inside the HTTP request that approved it; a crash between "approved" and
"executed", or a deploy, leaves work half done with nothing to resume it. At the same time, a demo or a small
deployment should not need a workflow engine.

## Decision
1. **Optional.** Temporal is off by default (`CASEPILOT_TEMPORAL_ENABLED=false`, extra `temporal`). Without it,
   processing and approval run inline, as before.
2. **Stateless graphs, durable workflow.** The agent graphs stay stateless; durability is the workflow's job.
   `CaseWorkflow` (`app/temporal/workflow.py`) runs `process_case_activity`, waits for the `review_submitted`
   signal (up to `REVIEW_TIMEOUT = 7 days`) when a HITL item was opened, then runs `finalize_review_activity`.
3. **Signal-driven approval.** With Temporal on, `hitl.review` validates and commits the decision, then signals
   the item's workflow; it does not execute the call. The worker executes it.
4. **Run-once writes.** Activities wrap the same services as the inline path. `finalize_review_activity` only
   acts on an item still `approved`/`rejected`; `process_case_activity` returns the existing outcome if the case
   already has an item from the same workflow. The write activity has a bounded retry policy (3 attempts) with
   `NotFound` and `Invalid` non-retryable.
5. **One workflow per case**, id `case-<case id>`, on `CASEPILOT_TEMPORAL_TASK_QUEUE`. Self-hosted or Temporal
   Cloud (API key + TLS).

## Consequences
- Approvals survive API restarts and deploys; the wait and the write are visible in the Temporal UI.
- Behaviour is identical with and without Temporal because the activities call the same services.
- Two processes (API and worker) must share the database and configuration; per-process adapters (the
  in-memory booking backend, in-memory memory) are not shared between them.
- A backend call that succeeds just before a worker crash can be repeated by the retry; booking backends should
  accept an idempotency key.
- After `REVIEW_TIMEOUT`, the workflow closes while the item stays `pending`; a later review cannot be signalled,
  so the API finalizes it inline instead (see [temporal.md](../temporal.md#timeout)).
- Only case-driven items use workflows; A2A, chat and MCP items are finalized inline.

## Alternatives considered
| Option | Why not |
|---|---|
| Always require Temporal | Breaks the zero-dependency demo and the offline test suite. |
| A database-polling job runner | Reinvents timers, retries and visibility that Temporal provides. |
| Checkpointed agent graphs (persist graph state, resume on approval) | Couples durability to one graph library and re-enters the model after approval, which ADR-002 rules out. |
| Run the whole agent loop as Temporal activities per model call | Finer durability than needed; the unit of work that must not be lost is "process" and "apply approved call". |

## Implementation notes
- Workflow, signal, query, retry policies: `apps/api/app/temporal/workflow.py`.
- Activities: `apps/api/app/temporal/activities.py`.
- Client (start, signal, Temporal Cloud): `apps/api/app/temporal/client.py`.
- Worker: `apps/api/app/temporal/worker.py` (`make worker`).
- Wiring: `apps/api/app/routers/cases.py` (start), `apps/api/app/services/hitl.py` (signal on review).
- Local server: `docker-compose.yml` profile `temporal` (`make temporal`).
- Test: `apps/api/tests/test_temporal_workflow.py` (time-skipping test server).
