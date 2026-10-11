# Contributing to casepilot

Thanks for helping. This guide covers setup, the checks a PR must pass, commit conventions, the decision-record
rule, and how to add agents and integrations.

## Setup

Prerequisites: [uv](https://docs.astral.sh/uv/) (Python 3.12 is installed by uv from `apps/api/.python-version`),
Node.js 22+ with npm, and Docker for Postgres (and optionally Temporal).

```bash
make install        # API with all extras (uv sync --all-extras) + admin (npm ci)
cp apps/api/.env.example apps/api/.env      # optional; defaults run offline
make dev            # Postgres + migrations + API :8000 + admin :5173
make demo           # or: no Docker at all (SQLite + mocks, API only)
make help           # every target
```

Everything runs offline by default: mock LLM, mock case source, in-memory backends. You never need an API key
to develop or to run the tests.

## Checks

```bash
make check          # what CI runs: lint + tests + eval + admin build
```

| Target | Runs |
|---|---|
| `make lint` | `ruff check` + `ruff format --check` (API); `npm run lint` + `npx tsc -b` (admin) |
| `make format` | `ruff format` + `ruff check --fix` |
| `make test` | `pytest -v` (API) and `npm test` (admin) |
| `make eval` | offline routing eval; fails below 0.9 accuracy |

Single API test: `cd apps/api && uv run pytest -v tests/test_case_processor.py::test_shadow_mode_proposes_instead_of_writing`.

Type-check the admin with `npx tsc -b`, not `tsc --noEmit` (the root `tsconfig.json` is references-only, so
`--noEmit` checks nothing).

Tests that need an optional SDK use `pytest.importorskip`, so they skip on a core-only install (`uv sync`) and
run with `uv sync --all-extras`. CI runs both.

## Commits and PR titles

[Conventional Commits](https://www.conventionalcommits.org/). PR titles are checked by `.github/workflows/pr-title.yaml`
and become the squash-merge message.

```
type(scope): short description in the imperative

feat(agents): add a documents agent
fix(api): return 409 when a case already has an open HITL item
docs: explain the go-live ramp
```

- Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `ci`, `build`.
- Scopes (optional): `api`, `admin`, `agents`, `runtime`, `protocols`, `temporal`, `docs`, `ci`, `deps`.

## The decision-record rule

A change to **agent behaviour, a protocol surface, the data model, an integration or a security boundary**
needs a decision record before the code is merged:

- a contained decision with a clear winner → an **ADR**;
- a big or cross-cutting decision → an **RFD** first, then an ADR once it is accepted.

Templates, numbering and statuses: [docs/decisions/README.md](docs/decisions/README.md). The PR template asks
you to link the record or say why none is needed.

## Adding an agent

Follow [docs/agent-plugin-contract.md](docs/agent-plugin-contract.md): an `AgentPlugin` registered at import
time, tools declared with `@tool(agent_scopes=[...], scope=...)`, a `@mock_script` so it runs offline, the
module listed in `CASEPILOT_AGENT_MODULES`, routing cases in `apps/api/evals/routing.yaml`, and tests.

## Adding an integration

Follow [docs/integrations.md §3](docs/integrations.md#3-how-to-add-an-integration): a `Protocol`, an adapter that
imports its SDK lazily, a factory switch in `app/config.py` plus a `set_*` override, an optional extra in
`apps/api/pyproject.toml`, an offline test (mock transport or `importorskip`), and an entry in
`docs/integrations.md` and `docs/configuration.md`. Read the licence from the installed package metadata, not
from memory.

## Rules that reviewers check

- Every tool call goes through `app/agents/runtime/gate.py:execute_gated`. Nothing calls `ToolRegistry.execute`
  or a backend's write method directly.
- `write_allowed` is set by the platform, never derived from model output.
- New modules that open DB sessions use `app.database` (`get_db` in routers, `session_scope()` elsewhere).
- Every state change that matters emits an audit event (`app/audit.py:emit`) in the same transaction.
- No secrets, real customer data or internal hostnames in code, fixtures or logs. Use `@example.com` addresses.
- Update `apps/api/.env.example` and `docs/configuration.md` when you add a setting.

## Reporting security issues

Do not open a public issue; see [SECURITY.md](SECURITY.md).

By contributing you agree that your contributions are licensed under the [MIT licence](LICENSE).
