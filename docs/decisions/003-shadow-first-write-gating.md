# ADR-003: Shadow-first write gating through a single choke point

- **Status:** Accepted
- **Date:** 2026-10-09
- **Related:** [ADR-001](001-pluggable-agent-runtime.md), [ADR-002](002-confidence-gated-hitl.md)

## Context
casepilot changes real bookings. Tool calls can originate from four surfaces (case-driven REST, A2A, MCP, chat),
two agent runtimes and the HITL approval path. If each path enforced write permission on its own, one missed
check would let a model, or an external agent, write without approval. And no one should trust an automation
with writes before it has been seen to make the right decision on real traffic.

## Decision
1. **One gate.** Every tool execution goes through `app/agents/runtime/gate.py:execute_gated(name, arguments,
   *, write_allowed, caller)`: unknown tool → error; WRITE tool without `write_allowed` →
   `"Write operation blocked: write gating active"`; then the per-`(tool, caller)` rate limit. Nothing else calls
   `ToolRegistry.execute`.
2. **Permission is seeded by the platform, never by the model.** `write_allowed` lives in `SessionContext`
   (native) or ADK session state `cp:write_allowed`, set by the caller of `run_agent`. Only two places set it to
   `True`: the case processor (live mode, confident and complete extraction) and `hitl.finalize` (an approved
   call). A2A, chat and MCP always pass `False`; an MCP write becomes a HITL item.
3. **Withhold, then refuse.** Read-only sessions are not offered WRITE tools (`get_scoped_tools`), so the agent
   proposes; if a model calls one anyway, the gate refuses it.
4. **Shadow first.** `CASEPILOT_WRITE_MODE` defaults to `shadow`: case processing never writes and every write is a
   proposal. `live` lets confident, complete cases write; everything else still goes to HITL.
5. **Ramp per reason.** A reason goes live only after the eval gate and a shadow period; the scope of a live
   deployment is set with `CASEPILOT_OWNED_REASONS`.

## Consequences
- The write boundary is one function with one test file (`tests/test_tools_and_gate.py`), plus tests that a
  model calling an unoffered write tool is refused under both runtimes.
- A new surface or runtime is safe by default if it calls `execute_gated`; reviewers check exactly that.
- A fresh install cannot change a booking until someone sets `CASEPILOT_WRITE_MODE=live` or approves an item.
- `write_mode` is global; a per-reason ramp is a deployment topology (separate live and shadow deployments with
  different `CASEPILOT_OWNED_REASONS`), not a per-reason setting.
- The in-process rate limiter is per replica; it is a backstop, not a substitute for gateway limits.

## Alternatives considered
| Option | Why not |
|---|---|
| Per-surface permission checks | Duplicated logic; one omission is a silent bypass. |
| Let the model decide when to write (prompt rules) | Prompt rules are advisory; permission must be a fact the model cannot change. |
| Live by default, shadow opt-in | Puts the risk on the people who know the platform least (new installs). |
| A per-reason `write_mode` map | Useful later; today the owned-reasons list plus deployment split covers the ramp without a new setting. |

## Implementation notes
- Gate: `apps/api/app/agents/runtime/gate.py`; rate limits `apps/api/app/agents/rate_limit.py`.
- Tool withholding: `ToolRegistry.get_scoped_tools` in `apps/api/app/agents/tools.py`.
- Permission seeding: `apps/api/app/agents/case_processor.py`, `apps/api/app/services/hitl.py` (`finalize`),
  `apps/api/app/services/pipeline_service.py` (`write_allowed=False`), `apps/api/app/routers/mcp.py`.
- ADK: `GatedFunctionTool` and `STATE_WRITE_ALLOWED` in `apps/api/app/agents/runtime/adk_engine.py`.
- Settings: `write_mode`, `owned_reasons` in `apps/api/app/config.py`.
