# casepilot API

FastAPI service: the case pipeline, the agents, the HITL queue, and the REST / A2A / MCP / AG-UI surfaces.
See the [root README](../../README.md) for the architecture and [docs/](../../docs) for the guides.

```bash
uv sync --all-extras                 # or plain `uv sync` for the offline core only
cp .env.example .env
uv run alembic upgrade head          # Postgres (make db at the repo root)
uv run uvicorn app.main:app --reload --port 8000
uv run pytest -v                     # offline: SQLite, mock LLM, in-memory backends
uv run python evals/run_evals.py     # routing accuracy gate
uv run python -m app.temporal.worker # only with CASEPILOT_TEMPORAL_ENABLED=true
```

| Path | What lives there |
|---|---|
| `app/agents/` | plugin registry, tool registry, orchestrator, extraction, booking + tracking agents, case processor |
| `app/agents/runtime/` | `run_agent` dispatcher, native tool loop, Google ADK runtime, the tool gate |
| `app/agents/llm/` | `LLMClient` interface, deterministic mock, LiteLLM adapter |
| `app/agents/graphs/` | stateless graph shim, loop guard, the A2A/chat pipeline |
| `app/integrations/` | case source (mock, Salesforce), booking + tracking backends (in-memory) |
| `app/services/` | case lifecycle, HITL queue, interactive escalation |
| `app/routers/` | REST, A2A, MCP, AG-UI |
| `app/temporal/` | durable case workflow, activities, worker |
| `alembic/` | migrations |
| `evals/` | routing eval (offline + Promptfoo) |
