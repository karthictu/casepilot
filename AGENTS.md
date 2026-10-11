# AGENTS.md

Guidance for AI coding assistants working in this repository. Humans: see [CONTRIBUTING.md](CONTRIBUTING.md).

## What this is

casepilot is a reference implementation of a case-driven agent automation platform for container shipping:
CRM cases → pre-router (owned reasons) → extraction → confidence gate → booking agent, which executes or
proposes a write. Proposals go to a HITL queue; approval runs exactly the proposed call. One core, four
surfaces: case-driven REST, A2A, MCP, AG-UI chat. Everything external is optional and off by default.

## Commands

```bash
make install                 # uv sync --all-extras (apps/api) + npm ci (apps/admin)
make demo                    # API on :8000, SQLite + seeded cases + mocks, no Docker
make dev                     # Postgres + migrations + API :8000 + admin :5173
make check                   # lint + tests + eval + admin build (the CI gate)
make test-api                # cd apps/api && uv run pytest -v   (offline: in-memory SQLite, mock LLM)
make eval                    # offline routing eval, fails below 0.9
make format                  # ruff format + ruff check --fix
cd apps/api && uv run pytest -v tests/test_case_processor.py::test_live_mode_books_a_confident_complete_case
cd apps/admin && npx tsc -b  # NOT tsc --noEmit (root tsconfig is references-only)
make temporal && make worker # optional: Temporal dev server + worker (CASEPILOT_TEMPORAL_ENABLED=true)
```

Python 3.12, ruff line length 120, rules E/F/I/UP/B. pytest runs with `asyncio_mode = "auto"`.

## Architecture map (`apps/api/app`)

| Path | Role |
|---|---|
| `main.py`, `config.py` | App factory (loads plugins, optional create/seed); every `CASEPILOT_*` setting |
| `agents/plugin.py` | `AgentPlugin`, `registry`, `load_plugins()` (imports `CASEPILOT_AGENT_MODULES`) |
| `agents/tools.py` | `@tool` decorator, `ToolRegistry`, schema derivation |
| `agents/runtime/engine.py` | `run_agent()`: the only way to run a model; dispatches to `native.py` or `adk_engine.py` |
| `agents/runtime/gate.py` | `execute_gated()`: write gating + rate limits for every tool call |
| `agents/llm/` | `LLMClient` protocol, `MockLLM` + `@mock_script` scripts (`mock_scripts.py`), `LiteLLMClient` |
| `agents/graphs/` | `mini.py` stateless graph shim, `loop_guard.py`, `pipeline.py` (A2A/chat path), `state.py` |
| `agents/orchestrator.py`, `extraction.py`, `booking.py`, `tracking.py` | The bundled agents |
| `agents/case_processor.py` | The case path (pure; no DB writes) |
| `agents/guardrails.py`, `agents/rate_limit.py`, `agents/memory/` | PII redaction / denied topics, limits, memory |
| `services/` | `case_service` (pull/process/persist), `hitl` (submit/review/finalize), `pipeline_service` |
| `routers/` | `cases`, `hitl`, `audit`, `agents`, `health`, `a2a`, `mcp`, `agui` |
| `integrations/` | `case_source` (mock, Salesforce), `booking_backend`, `tracking_backend` (in-memory) |
| `temporal/` | `CaseWorkflow`, activities, client, worker |
| `models/`, `database.py`, `audit.py` | `Case`, `HitlItem`, `AuditEvent`; engine/sessions; `audit.emit()` |

Admin UI: `apps/admin` (React 19 + Vite + Tailwind 4; chat via assistant-ui over AG-UI).
Docs: `docs/` (start at `docs/README.md`). Decisions: `docs/decisions/`.

## Rules

1. **All tool calls go through the gate.** Use `execute_gated` (or `run_agent`, which uses it). Never call
   `ToolRegistry.execute`, a tool function, or a backend's write method directly from new code.
2. **Never derive `write_allowed` from model output.** It is seeded by the platform (live case processing above
   the threshold, or HITL approval). A2A, chat and MCP stay read-only.
3. **Approval runs the stored call.** Do not re-run a model after HITL approval.
4. **Call models through `run_agent`**, never a provider SDK, so guardrails, loop guard, cost cap and tracing apply.
5. **Scope every tool**: `@tool(..., agent_scopes=["<agent_id>"], scope="<oauth scope>")`. Empty `agent_scopes`
   offers the tool to every agent.
6. **New modules that open DB sessions use `app.database`** (`get_db` dependency in routers, `session_scope()`
   elsewhere). Do not create engines or sessionmakers of your own; the tests swap the database through it.
7. **Audit state changes** with `app.audit.emit(db, ...)` in the same transaction as the change.
8. **Integrations are adapters**: `Protocol` + factory `get_*` + `set_*` override + optional extra + offline test.
   Import optional SDKs lazily. Defaults must stay offline.
9. **New agent**: an `AgentPlugin` registered at import, a `@mock_script("<agent_id>")`, listed in
   `CASEPILOT_AGENT_MODULES`, routing cases in `evals/routing.yaml`. See `docs/agent-plugin-contract.md`.
10. **Decision trail**: changes to agent behaviour, a surface, the data model, an integration or a security
    boundary need an ADR in `docs/decisions/` (RFD first for cross-cutting ones).
11. **Conventional Commits** (`feat(agents): ...`); scopes `api admin agents runtime protocols temporal docs ci deps`.
12. **Fixtures and docs** use synthetic data only: `@example.com` addresses, `BK-1xxxxx` references.
13. **Verify by running**: run the tests or curl the endpoint and report the real output before calling a task done.

## Gotchas

- `tests/conftest.py` sets `CASEPILOT_*` env vars before importing the app and resets the booking backend,
  memory and rate limiter per test. Two tests assert the exact bundled agent set.
- The mock orchestrator only recognises the bundled intents (`_INTENT_PATTERNS` in `agents/llm/mock_scripts.py`).
- Factories cache per process; in-memory adapters are not shared between the API and a Temporal worker.
- `CASEPILOT_AUTO_CREATE_TABLES=true` skips Alembic, and with it the append-only trigger on `audit_events`.
