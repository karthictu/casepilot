# Evals and CI
*reference · last updated 2026-10-09*

## Purpose
What the routing evals measure, how to run them against the mock or a real model, and what each GitHub
workflow runs and when, for contributors and maintainers.

## TL;DR
- `make eval`: offline routing eval (`apps/api/evals/run_evals.py` over `evals/routing.yaml`, 13 cases); exits
  non-zero below the 0.9 accuracy threshold. Part of `make check`.
- `make eval-promptfoo`: the same idea through Promptfoo against a running API.
- Both work on the mock LLM (a deterministic contract test) or a real model (`CASEPILOT_LLM_PROVIDER=litellm`).
- Eight workflows: `ci-api`, `ci-admin`, `codeql`, `docker-publish`, `eval-gate`, `pr-title`, `stale`,
  `workflow-lint`. The only optional secret is `OPENAI_API_KEY` (manual real-model eval runs).
- Dependabot updates uv, npm, GitHub Actions and Docker base images weekly.

## The offline routing eval

```bash
make eval                                   # = cd apps/api && uv run python evals/run_evals.py
# PASS  track_shipment       got=track_shipment       Where is BK-100001 right now?
# ...
# {"cases": 13, "passed": 13, "accuracy": 1.0, "threshold": 0.9}

# Against a real model
cd apps/api && CASEPILOT_LLM_PROVIDER=litellm CASEPILOT_MODEL_INTENT=openai/gpt-4o-mini \
  OPENAI_API_KEY=... uv run python evals/run_evals.py
```

Each case in `evals/routing.yaml` is `{query, intent, route_to}`. The script loads the plugins, runs
`run_orchestrator(query)` for each and passes a case only if both the intent and the routed agent match. The
cases cover tracking, create, amend, cancel, status and two `unknown` → `hitl` cases. Add cases when you add an
intent or an agent.

What it guards: the orchestrator prompt built from the registry, the intent → agent routing table, and the
"unknown intent goes to a human" rule. On the mock LLM it is a contract test for that wiring; on a real model it
measures the prompt.

## Promptfoo

`apps/api/evals/promptfoo.routing.yaml` uses Promptfoo's HTTP provider against
`POST {CASEPILOT_API_URL or http://localhost:8000}/api/agents/orchestrator/classify` and asserts
`output.intent` and `output.route_to` with JavaScript assertions (6 cases).

```bash
make api                # terminal 1 (or make demo)
make eval-promptfoo     # terminal 2: npx --yes promptfoo@latest eval -c evals/promptfoo.routing.yaml
```

The classify endpoint requires a caller identity, so in `jwt` mode add an `Authorization` header to the
provider config. Point the API at a real model to evaluate it; Promptfoo's web viewer (`npx promptfoo view`)
compares runs.

## The CI gate locally

```bash
make check   # = make lint test eval, then npm run build in apps/admin
```

| Step | Runs |
|---|---|
| `make lint` | `ruff check .` and `ruff format --check .` (API); `npm run lint` and `npx tsc -b` (admin) |
| `make test` | `pytest -v` (API, offline); `npm test` (Vitest, admin) |
| `make eval` | the offline routing eval |
| build | `npm run build` (admin) |

Use `npx tsc -b`, not `tsc --noEmit`: the admin's root `tsconfig.json` only holds project references, so
`--noEmit` against it checks nothing.

## GitHub workflows

| Workflow | Triggers | What it runs | Secrets / vars |
|---|---|---|---|
| `ci-api.yaml` | push to `main` and PRs touching `apps/api/**` or the workflow | **lint**: `uv sync --frozen`, `ruff check`, `ruff format --check`. **test**: matrix Python 3.12 / 3.13 × extras `core` / `all`, `pytest -v -rs` (optional-SDK tests skip on `core`). **migrations**: Postgres 16 service, `alembic upgrade head` → `downgrade base` → `upgrade head`, then checks that `audit_events` rejects a `DELETE` | none |
| `ci-admin.yaml` | push to `main` and PRs touching `apps/admin/**` or the workflow | Node 22: `npm ci`, `npm run lint`, `npx tsc -b`, `npm test`, `npm run build` | none |
| `codeql.yaml` | push to `main`, every PR, weekly (Mondays 03:17 UTC) | CodeQL `security-and-quality` for `python`, `javascript-typescript` and `actions` | none (`security-events: write`) |
| `docker-publish.yaml` | push to `main`, `v*` tags, PRs touching `apps/**` | Builds `apps/api` and `apps/admin` images with Buildx (GHA cache); pushes `ghcr.io/<owner>/<repo>-api` / `-admin` except on PRs; tags: branch, semver `X.Y.Z` and `X.Y`, sha | built-in `GITHUB_TOKEN` (`packages: write`) |
| `eval-gate.yaml` | PRs touching `apps/api/app/agents/**` or `apps/api/evals/**`; manual `workflow_dispatch` with input `provider` (`mock` default, or `litellm`) | **routing**: `uv sync --frozen --all-extras`, `run_evals.py`, uploads `routing-eval.txt`. **promptfoo**: starts the API on SQLite (`CASEPILOT_AUTO_CREATE_TABLES=true`), waits for `/health`, runs Promptfoo, uploads `promptfoo-results.json` | optional secret `OPENAI_API_KEY` and repo variable `CASEPILOT_MODEL_INTENT` (default `openai/gpt-4o-mini`), used by the routing job when dispatched with `provider=litellm` |
| `pr-title.yaml` | `pull_request_target` (opened, edited, synchronize, reopened) | `amannn/action-semantic-pull-request`: Conventional Commits title; types `feat fix refactor perf docs test chore ci build`; scopes `api admin agents runtime protocols temporal docs ci deps`; scope optional | built-in `GITHUB_TOKEN` (read-only; no checkout) |
| `stale.yaml` | daily 04:30 UTC, manual | Marks issues and PRs stale after 60 days, closes 14 days later; exempt labels `pinned`, `security` (issues) and `pinned` (PRs) | built-in `GITHUB_TOKEN` |
| `workflow-lint.yaml` | PRs touching `.github/workflows/**` | Downloads and runs `actionlint` | none |

Notes:

- Both jobs switch provider on manual dispatch (`provider: litellm` uses the `OPENAI_API_KEY` secret and the
  `CASEPILOT_MODEL_INTENT` repository variable); pull requests always run on the mock LLM.
- The `routing` step sets `shell: bash` (`bash -eo pipefail`), so a below-threshold eval fails the step even
  though its output is piped through `tee`.

## Dependabot

`.github/dependabot.yml`, all weekly:

| Ecosystem | Directory | Grouping | Commit prefix |
|---|---|---|---|
| `uv` | `/apps/api` | group `python`: all minor + patch updates | `chore(deps)` |
| `npm` | `/apps/admin` | group `npm`: all minor + patch updates | `chore(deps)` |
| `github-actions` | `/` | none | `ci` |
| `docker` | `/apps/api`, `/apps/admin` | none | `chore(deps)` |

Major updates arrive as individual PRs. Two admin pins need care: `@ag-ui/client` stays on the `0.0.x` line that
`@assistant-ui/react-ag-ui` depends on, and TypeScript stays on `6.0.x` until typescript-eslint supports 7
(`apps/admin/README.md`).

## Related
- [CONTRIBUTING.md](../CONTRIBUTING.md)
- [hitl-and-shadow-mode.md](hitl-and-shadow-mode.md#the-go-live-ramp): the eval gate in the go-live ramp
- [integrations.md](integrations.md): Promptfoo, GitHub Actions, CodeQL, Dependabot, actionlint
