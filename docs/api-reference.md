# API reference
*reference · last updated 2026-10-09*

## Purpose
The HTTP contract between the casepilot API (`apps/api`), the admin UI (`apps/admin`) and external agents.
Read this when you call the API or change a route.

## TL;DR
- Base URL in local dev: `http://localhost:8000`. The admin UI runs on `http://localhost:5173` and proxies
  `/api`, `/a2a`, `/mcp`, `/.well-known` and `/health` to the API.
- Auth: with `CASEPILOT_AUTH_MODE=mock` (the default) no header is needed and the caller is `dev-operator` with
  every scope. With `jwt`, send `Authorization: Bearer <token>`; scopes come from the token's `scope` / `scp`
  claim, and every `/api/cases`, `/api/hitl` and `/api/audit` route needs `casepilot.operator`.
- Four ingress surfaces over one core: **case-driven** (`/api/cases/*`), **A2A** (`/a2a`), **MCP** (`/mcp`) and
  **chat** (`/api/agui`, AG-UI over SSE).
- Writes are gated: a request that would change a booking without permission becomes a **HITL item** that an
  operator approves at `POST /api/hitl/queue/{id}/review`.
- Every response carries an `X-Request-ID` header (the inbound one if you sent it); audit events record it.

## Shapes

```ts
type CaseStatus = 'new' | 'skipped' | 'processing' | 'hitl_required' | 'booked' | 'failed' | 'rejected'

interface Case {
  id: string                 // uuid
  external_id: string        // id in the source CRM
  subject: string
  description: string
  from_address: string
  reason: string             // the CRM's "reason for case" value, e.g. "booking_create"
  status: CaseStatus
  intent: string | null      // extracted intent; null until processed, and for skipped cases
  confidence: number | null  // null until processed, and for skipped cases
  booking_ref: string | null
  hitl_item_id: string | null  // the latest HITL item opened for this case
  result: CaseProcessingResult | null
  created_at: string         // ISO-8601
  updated_at: string
}

interface CaseProcessingResult {
  case_id: string
  status: CaseStatus
  intent: string             // "unknown" when nothing was extracted
  reason: string
  confidence: number
  needs_hitl: boolean
  hitl_reason: string        // why it was escalated or skipped
  hitl_action: string | null // the proposed tool name, or "manual_review"; null when not escalated
  proposed_call: { tool: string; arguments: Record<string, unknown> } | null
  booking_ref: string | null
  booking_outcome: 'executed' | 'answered' | 'hitl_required' | 'failed' | null  // null when skipped / not run
  shadow: boolean            // true when the run was not allowed to write
  extraction: Record<string, unknown>  // BookingExtraction, incl. missing_fields
  decision: Record<string, unknown>    // the booking agent's decision (incl. _diagnostics)
}

type HitlStatus = 'pending' | 'approved' | 'rejected' | 'executed' | 'failed'

interface HitlItem {
  id: string
  source: 'case' | 'a2a' | 'mcp' | 'chat'
  source_ref: string         // case id, A2A task id, chat thread id, or a generated id for MCP
  agent_id: string           // e.g. "booking"
  action: string             // the tool to run, e.g. "booking_create", or "manual_review"
  payload: {
    tool: string | null      // exactly what runs on approval (null for manual_review until an operator supplies it)
    arguments: Record<string, unknown> | null
    context: Record<string, unknown>   // case id + subject + extraction, the query, or the MCP caller
    original?: { tool: string | null; arguments: Record<string, unknown> | null }  // set when the operator corrected it
  }
  confidence: number
  reason: string
  status: HitlStatus
  reviewer: string | null
  reviewer_note: string | null
  result: ToolCallResult | null   // set once the approved call ran
  workflow_id: string | null      // set when the case runs as a Temporal workflow
  created_at: string
  reviewed_at: string | null
}

interface ToolCallResult {
  id: string
  name: string
  arguments: Record<string, unknown>
  result: unknown            // e.g. the booking, with booking_ref
  error: string | null
  duration_ms: number
}

interface AgentInfo {        // AgentPlugin.to_dict()
  agent_id: string
  display_name: string
  description: string
  version: string
  owner_team: string
  intents: string[]
  scopes: string[]
  write_capable: boolean
  requires_hitl: boolean
  hitl_confidence_threshold: number
}

interface ToolInfo {         // ToolDefinition.to_dict()
  name: string
  description: string
  operation_type: 'read' | 'write'
  agent_scopes: string[]
  scope: string | null       // OAuth scope required over MCP
  parameters: Record<string, unknown>  // JSON Schema
}

interface AuditEvent {
  id: string
  event_type: string         // cases.pulled, case.<status>, hitl.submitted|approved|rejected|executed|failed, a2a.request, chat.request, mcp.tool_call
  actor: string
  surface: 'case_driven' | 'a2a' | 'mcp' | 'chat' | 'admin'
  request_id: string | null
  payload: Record<string, unknown>   // PII-redacted
  created_at: string
}

interface RuntimeConfig {
  version: string
  auth_mode: 'mock' | 'jwt'
  write_mode: 'shadow' | 'live'
  agent_runtime: 'native' | 'adk'
  llm_provider: 'mock' | 'litellm'
  case_source: 'mock' | 'salesforce'
  memory_backend: 'inmemory' | 'mem0'
  temporal_enabled: boolean
  langfuse_enabled: boolean
}
```

## Errors

Service errors map to HTTP status codes (`app/routers/_errors.py`); the body is FastAPI's `{"detail": "..."}`.

| Status | When |
|---|---|
| 401 | `jwt` mode: missing or invalid bearer token |
| 403 | Token lacks the required scope (`casepilot.operator` for operator routes) |
| 404 | Unknown case, HITL item or A2A task |
| 409 | Case is `processing` or `booked`, or already has a `pending`/`approved` HITL item; HITL item is no longer `pending` |
| 422 | Request validation failed; or approving an item with nothing valid to execute (no `tool`, or a tool that does not exist) |

## Endpoints

"Auth" is what `jwt` mode requires; in `mock` mode every check passes.

### Platform

| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/health` | none | `{ status: "ok", version }` |
| GET | `/api/config` | none | `RuntimeConfig` |
| GET | `/api/agents` | none | `{ items: AgentInfo[] }` |
| GET | `/api/tools` | none | `{ items: ToolInfo[] }` |
| POST | `/api/agents/orchestrator/classify` | any valid token | body `{ query }` → `{ intent, confidence, route_to, reasoning }` (`route_to` is an `agent_id` or `"hitl"`) |
| GET | `/api/audit?limit=100&event_type=` | operator | `{ items: AuditEvent[] }`, newest first; `limit` ≤ 1000 |

### Case-driven ingress

| Method | Path | Auth | Returns |
|---|---|---|---|
| POST | `/api/cases/pull` | operator | `{ pulled, created }`: fetch new cases from the configured case source (dedupe on `external_id`) |
| GET | `/api/cases?status=&limit=100` | operator | `{ items: Case[], total }`, newest first; `limit` ≤ 500; `total` counts all matching cases |
| GET | `/api/cases/{id}` | operator | `Case` |
| POST | `/api/cases/{id}/process` | operator | `{ case: Case, result: CaseProcessingResult }`. With Temporal enabled: `{ case, workflow_id }`, where `case` is the state **before** processing |

### Human in the loop

| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/api/hitl/queue?status=pending` | operator | `{ items: HitlItem[] }`, newest first, up to 200 (omit `status` for all) |
| GET | `/api/hitl/queue/{id}` | operator | `HitlItem` |
| POST | `/api/hitl/queue/{id}/review` | operator | body `ReviewRequest` → `HitlItem` |

```ts
interface ReviewRequest {
  decision: 'approve' | 'reject'
  note?: string | null
  // Optional corrections, applied on approve only. Required for `manual_review` items.
  tool?: string | null                       // replaces payload.tool
  arguments?: Record<string, unknown> | null // replaces payload.arguments
}
```

Approving runs `payload.tool` with `payload.arguments` through the gate with write permission; the model is
not re-run. If `tool` or `arguments` is given, the payload is updated first and the previous values are kept in
`payload.original`. The item ends `executed` or `failed`, and a linked case moves to `booked` or `failed`.
Rejecting moves a linked case to `rejected`. With Temporal enabled and an item that belongs to a workflow, the
response shows `approved` and the workflow finishes the execution.

### A2A (agent-to-agent)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/.well-known/agent.json` | none | Agent card: name, url, version, capabilities, skills (one per registered agent), auth schemes |
| POST | `/a2a/tasks/send` | any valid token | body `{ id?, sessionId?, message: { role: "user", parts: [{ type: "text", text }] }, metadata? }` → Task |
| GET | `/a2a/tasks/{id}` | any caller; owner only (404 for others) | Task, refreshed from the HITL item once it has been reviewed |

A task's `status.state` is `completed`, `input-required` (escalated to HITL; `metadata.hitl_item_id` is set),
`failed`, or, after review, `rejected`. The answer is in `artifacts[0].parts[0].text` and
`status.message.parts[0].text`; `metadata` carries `intent`, `confidence`, `route_to` and `hitl_item_id`. Tasks
are kept in process memory. Details: [protocols.md](protocols.md#a2a).

### MCP (Model Context Protocol, JSON-RPC 2.0 over HTTP)

`POST /mcp` (auth: any valid token) with methods `initialize`, `ping`, `tools/list`, `tools/call`. A request
without an `id` (a notification) gets HTTP 202 and no body.

- `tools/list` returns only the tools whose `scope` the caller's token holds, with `inputSchema` and
  `annotations.readOnlyHint`.
- `tools/call` runs a **read** tool directly and returns its JSON as a text content block (`isError: true` if the
  tool returned an error).
- A **write** tool is never executed here: it creates a HITL item and returns
  `{"content": [{"type": "text", "text": "{\"status\": \"pending_approval\", \"hitl_item_id\": \"<uuid>\"}"}], "isError": false}`.
- Errors: `-32601` unknown method, `-32602` unknown tool, `-32003` missing scope.

Details: [protocols.md](protocols.md#mcp).

### Chat (AG-UI over SSE)

`POST /api/agui` (auth: any valid token) with an AG-UI `RunAgentInput`:

```json
{ "threadId": "t1", "runId": "r1", "messages": [{ "id": "m1", "role": "user", "content": "Where is BK-100001?" }],
  "tools": [], "context": [], "state": {}, "forwardedProps": {} }
```

The response is `text/event-stream`, one JSON event per `data:` frame:
`RUN_STARTED → STEP_STARTED/STEP_FINISHED (orchestrator, then the specialist if one ran) →
(TOOL_CALL_START → TOOL_CALL_ARGS → TOOL_CALL_END → TOOL_CALL_RESULT)* → TEXT_MESSAGE_START → TEXT_MESSAGE_CONTENT+ →
TEXT_MESSAGE_END → CUSTOM{name:"hitl", value:{hitl_item_id, action, reason}}? → RUN_FINISHED`, or
`RUN_STARTED → RUN_ERROR{message}`. Details: [protocols.md](protocols.md#ag-ui).

## Related

- [architecture.md](architecture.md)
- [protocols.md](protocols.md)
- [hitl-and-shadow-mode.md](hitl-and-shadow-mode.md)
- [configuration.md](configuration.md)
