# Configuration
*reference · last updated 2026-10-09*

## Purpose
Every `CASEPILOT_*` setting in `apps/api/app/config.py`, with its type, default and effect, for anyone deploying
casepilot or switching an integration on.

## TL;DR
- Settings are read by pydantic-settings from environment variables prefixed `CASEPILOT_` (case-insensitive),
  or from a `.env` file in the API's working directory (`apps/api/.env`; start from `apps/api/.env.example`).
- List values are JSON: `CASEPILOT_OWNED_REASONS=["booking_create","booking_cancel"]`.
- The defaults run fully offline: mock auth, mock LLM, native runtime, mock case source, in-memory memory,
  shadow writes, no Temporal, no LangFuse.
- `GET /api/config` reports the active `auth_mode`, `write_mode`, `agent_runtime`, `llm_provider`, `case_source`,
  `memory_backend`, `temporal_enabled` and `langfuse_enabled` (the admin top bar shows them as badges).
- Provider credentials (OpenAI, AWS, Azure) use LiteLLM's own variables, not `CASEPILOT_*`
  ([integrations.md](integrations.md#llm-providers-via-litellm-aws-bedrock-azure-openai-openai)).

## Application

| Variable | Type | Default | Meaning |
|---|---|---|---|
| `CASEPILOT_APP_NAME` | str | `casepilot` | FastAPI title, A2A agent card `name`, MCP `serverInfo.name` |
| `CASEPILOT_LOG_LEVEL` | str | `INFO` | Python logging level (API and worker) |
| `CASEPILOT_CORS_ORIGINS` | list[str] | `["http://localhost:5173"]` | Allowed CORS origins (credentials allowed). Not needed when the admin proxies same-origin. |

## Database

| Variable | Type | Default | Meaning |
|---|---|---|---|
| `CASEPILOT_DATABASE_URL` | str | `postgresql+asyncpg://casepilot:casepilot@localhost:5432/casepilot` | SQLAlchemy async URL. `sqlite+aiosqlite:///./casepilot.db` for a local file. Also used by Alembic. |
| `CASEPILOT_AUTO_CREATE_TABLES` | bool | `false` | Create tables at startup (`Base.metadata.create_all`) instead of running Alembic. For SQLite demos; leave off for Postgres (it skips the append-only trigger). |
| `CASEPILOT_SEED_ON_STARTUP` | bool | `false` | Pull cases from the configured case source at startup (actor `startup`). |

## Auth

| Variable | Type | Default | Meaning |
|---|---|---|---|
| `CASEPILOT_AUTH_MODE` | `mock` \| `jwt` | `mock` | `mock`: every request is `dev-operator` with all scopes (**development only**). `jwt`: require a verified bearer token. |
| `CASEPILOT_JWT_SECRET` | str \| None | None | HS256 shared secret (use at least 32 bytes). |
| `CASEPILOT_JWT_JWKS_URL` | str \| None | None | JWKS URL for RS256/ES256 tokens from any OIDC provider. Takes precedence over the secret. |
| `CASEPILOT_JWT_AUDIENCE` | str \| None | None | Expected `aud`; audience is verified only when set. |
| `CASEPILOT_JWT_ISSUER` | str \| None | None | Expected `iss`. |

Scopes come from the token's `scope` (space-separated string) or `scp` (list) claim. Operator routes need
`casepilot.operator`; MCP tools need their own `scope` ([tools-and-gating.md](tools-and-gating.md)).

## Agent behaviour

| Variable | Type | Default | Meaning |
|---|---|---|---|
| `CASEPILOT_WRITE_MODE` | `shadow` \| `live` | `shadow` | `shadow`: case processing never writes; every write becomes a HITL proposal. `live`: confident, complete cases write. Interactive surfaces never write in either mode. |
| `CASEPILOT_HITL_CONFIDENCE_THRESHOLD` | float | `0.85` | Below this, case processing and the bundled agents escalate. Also the booking plugin's `hitl_confidence_threshold`, read once when the plugin registers. |
| `CASEPILOT_OWNED_REASONS` | list[str] | `["booking_create","booking_amend","booking_cancel"]` | CRM reasons the case processor handles; any other case is `skipped`. |
| `CASEPILOT_AGENT_MODULES` | list[str] | `["app.agents.booking","app.agents.tracking"]` | Modules imported at startup; each registers an `AgentPlugin` ([agent-plugin-contract.md](agent-plugin-contract.md)). |
| `CASEPILOT_MAX_COST_USD_PER_RUN` | float | `0.50` | LLM cost cap per `run_agent` call; `0` disables it. Costs come from LiteLLM; the mock reports 0. |

## Agent runtime and LLM

| Variable | Type | Default | Meaning |
|---|---|---|---|
| `CASEPILOT_AGENT_RUNTIME` | `native` \| `adk` | `native` | Tool loop implementation. `adk` needs the `adk` extra. |
| `CASEPILOT_LLM_PROVIDER` | `mock` \| `litellm` | `mock` | `mock`: deterministic offline scripts. `litellm`: real models (needs the `litellm` extra). |
| `CASEPILOT_MODEL_INTENT` | str | `openai/gpt-4o-mini` | LiteLLM model string for the orchestrator. |
| `CASEPILOT_MODEL_EXTRACTION` | str | `openai/gpt-4o-mini` | Model for the extraction agent. |
| `CASEPILOT_MODEL_REASONING` | str | `openai/gpt-4o` | Model for the booking and tracking agents (and the documented plugin pattern). |
| `CASEPILOT_LITELLM_API_BASE` | str \| None | None | Send every call through a LiteLLM proxy at this URL; model strings become proxy aliases (prefixed `litellm_proxy/`). |
| `CASEPILOT_LITELLM_API_KEY` | str \| None | None | Key for that proxy. |

## Memory

| Variable | Type | Default | Meaning |
|---|---|---|---|
| `CASEPILOT_MEMORY_BACKEND` | `inmemory` \| `mem0` | `inmemory` | Customer memory recalled into the orchestrator prompt. `inmemory` is per process and not persistent. |
| `CASEPILOT_MEM0_CONFIG_JSON` | str \| None | None | JSON passed to Mem0 `AsyncMemory.from_config`, e.g. a pgvector store and your embedding provider. Empty uses Mem0's defaults (OpenAI). |

## Case source

| Variable | Type | Default | Meaning |
|---|---|---|---|
| `CASEPILOT_CASE_SOURCE` | `mock` \| `salesforce` | `mock` | `mock` serves `app/seeds/sample_cases.json`. |
| `CASEPILOT_SALESFORCE_LOGIN_URL` | str | `https://login.salesforce.com` | OAuth host (use `https://test.salesforce.com` for sandboxes). Also the JWT `aud`. |
| `CASEPILOT_SALESFORCE_CLIENT_ID` | str \| None | None | Connected app consumer key (JWT `iss`). |
| `CASEPILOT_SALESFORCE_USERNAME` | str \| None | None | Integration user (JWT `sub`). |
| `CASEPILOT_SALESFORCE_PRIVATE_KEY_PATH` | str \| None | None | PEM private key matching the connected app's certificate. |
| `CASEPILOT_SALESFORCE_API_VERSION` | str | `v61.0` | REST API version in `/services/data/<version>/query`. |
| `CASEPILOT_SALESFORCE_CASE_FILTER` | str \| None | None | Extra SOQL condition ANDed into the query, e.g. `Origin = 'Email' AND Status = 'New'`. |

## Observability

| Variable | Type | Default | Meaning |
|---|---|---|---|
| `CASEPILOT_LANGFUSE_ENABLED` | bool | `false` | Use the LangFuse tracer (needs the `langfuse` extra). |
| `CASEPILOT_LANGFUSE_PUBLIC_KEY` | str \| None | None | Project public key. |
| `CASEPILOT_LANGFUSE_SECRET_KEY` | str \| None | None | Project secret key. |
| `CASEPILOT_LANGFUSE_HOST` | str | `http://localhost:3000` | Self-hosted server or LangFuse Cloud URL. |

The audit trail is also logged as one JSON line per event on the `casepilot.audit` logger, whatever the tracer.

## Temporal

| Variable | Type | Default | Meaning |
|---|---|---|---|
| `CASEPILOT_TEMPORAL_ENABLED` | bool | `false` | Run case processing as `CaseWorkflow` and finalize approvals in the worker. Set it on the API **and** the worker. |
| `CASEPILOT_TEMPORAL_ADDRESS` | str | `localhost:7233` | Temporal frontend (gRPC) address. |
| `CASEPILOT_TEMPORAL_NAMESPACE` | str | `default` | Namespace (`<namespace>.<account>` on Temporal Cloud). |
| `CASEPILOT_TEMPORAL_TASK_QUEUE` | str | `casepilot` | Task queue the worker polls and workflows are started on. |
| `CASEPILOT_TEMPORAL_API_KEY` | str \| None | None | Temporal Cloud API key; implies TLS. |
| `CASEPILOT_TEMPORAL_TLS` | bool | `false` | TLS without an API key. |

## Admin UI (build-time, `apps/admin`)

Not `CASEPILOT_*`, but part of a deployment:

| Variable | Default | Meaning |
|---|---|---|
| `VITE_API_BASE_URL` | empty (same origin) | API base URL compiled into the bundle |
| `VITE_API_TOKEN` | empty | Optional bearer token sent on every call; compiled into the bundle, so never a long-lived secret |
| `VITE_API_PROXY_TARGET` | `http://localhost:8000` | Dev/preview proxy target |
| `API_UPSTREAM` (container) | `http://api:8000` | Where the admin image's nginx proxies `/api`, `/a2a`, `/mcp`, `/.well-known`, `/health` |

## Example profiles

```bash
# Zero-dependency demo (what `make demo` sets)
CASEPILOT_DATABASE_URL=sqlite+aiosqlite:///./casepilot-demo.db
CASEPILOT_AUTO_CREATE_TABLES=true
CASEPILOT_SEED_ON_STARTUP=true

# Real model through LiteLLM, still shadow
CASEPILOT_LLM_PROVIDER=litellm
CASEPILOT_MODEL_INTENT=openai/gpt-4o-mini
CASEPILOT_MODEL_EXTRACTION=openai/gpt-4o-mini
CASEPILOT_MODEL_REASONING=openai/gpt-4o
OPENAI_API_KEY=...

# A shared deployment
CASEPILOT_AUTH_MODE=jwt
CASEPILOT_JWT_JWKS_URL=https://your-idp.example.com/.well-known/jwks.json
CASEPILOT_JWT_AUDIENCE=casepilot
CASEPILOT_JWT_ISSUER=https://your-idp.example.com/
CASEPILOT_CORS_ORIGINS=["https://casepilot.example.com"]
```

## Related
- [integrations.md](integrations.md): what each switch connects to
- [temporal.md](temporal.md), [hitl-and-shadow-mode.md](hitl-and-shadow-mode.md)
- `apps/api/.env.example`
