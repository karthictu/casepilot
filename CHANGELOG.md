# Changelog

All notable changes to casepilot are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-09

Initial release.

### Added
- **Case-driven pipeline**: pull cases from a case source (`POST /api/cases/pull`), process them
  (`POST /api/cases/{id}/process`) through pre-router → extraction → confidence gate → booking agent.
- **Shadow-first writes**: `CASEPILOT_WRITE_MODE=shadow` by default; every write becomes a HITL proposal.
- **HITL queue** (`/api/hitl/queue`): propose-then-approve, approval executes the stored call verbatim, operator
  corrections with `payload.original`, `manual_review` items.
- **Agents**: orchestrator (registry-driven routing), extraction (code-computed completeness), booking
  (create / amend / cancel / status, invariant enforcement), tracking (read-only); `AgentPlugin` registry and
  `CASEPILOT_AGENT_MODULES`.
- **Tool system**: `@tool` decorator, READ/WRITE, `agent_scopes` and OAuth `scope`, schema derivation, one gate
  for every call (write gating + rate limits), loop guard, cost cap, PII redaction and denied topics.
- **Surfaces**: A2A agent card and tasks, MCP JSON-RPC (`initialize`, `ping`, `tools/list`, `tools/call`;
  writes become HITL items), AG-UI chat over SSE.
- **Runtimes**: native tool loop (default) and Google ADK (`CASEPILOT_AGENT_RUNTIME=adk`).
- **Integrations** (all optional, off by default): LiteLLM, LangFuse, Mem0, Temporal (durable `CaseWorkflow`
  with signal-driven approval), Salesforce case source (JWT bearer + SOQL).
- **Persistence**: `cases`, `hitl_items`, `audit_events` with an append-only trigger on Postgres; Alembic
  migration `001`.
- **Auth**: mock mode for development; JWT (HS256 or JWKS) with scopes; `casepilot.operator` for operator routes.
- **Admin UI**: React 19 + Vite + Tailwind 4 console with Dashboard, Cases, Case detail, HITL queue,
  Agents & Tools, Chat (assistant-ui over AG-UI) and Audit log.
- **Evals and CI**: offline routing eval and Promptfoo config; workflows for API, admin, CodeQL, image
  publishing to GHCR, eval gate, PR titles, stale issues and workflow lint; Dependabot.
- **Docs**: architecture, case pipeline, HITL and shadow mode, protocols, plugin contract, tools and gating,
  integrations, Temporal, configuration, evals and CI, API reference, ADR-001 to ADR-005.

### Known limitations
- A2A tasks are kept in process memory (per replica).
- Approved writes carry no idempotency key to the booking backend, so a worker crash between the backend call and
  the commit can repeat the call on retry ([docs/temporal.md](docs/temporal.md)).
- The bundled in-memory booking/tracking backends are per process; use a real adapter when the Temporal worker
  and the API run separately.

[Unreleased]: https://github.com/OWNER/casepilot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OWNER/casepilot/releases/tag/v0.1.0
