API   := apps/api
ADMIN := apps/admin
UV    := cd $(API) && uv run

.PHONY: help install dev demo db db-stop migrate api admin worker temporal test test-api test-admin lint format check eval eval-promptfoo clean

help: ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

install: ## install API (all extras) + admin dependencies
	cd $(API) && uv sync --all-extras
	cd $(ADMIN) && npm ci

demo: ## zero-dependency demo: SQLite + seeded cases + mocks, API on :8000
	cd $(API) && CASEPILOT_DATABASE_URL=sqlite+aiosqlite:///./casepilot-demo.db CASEPILOT_AUTO_CREATE_TABLES=true \
		CASEPILOT_SEED_ON_STARTUP=true uv run uvicorn app.main:app --port 8000

dev: db migrate ## Postgres + API (:8000) + admin (:5173) with hot reload
	$(MAKE) -j2 api admin

db: ## start Postgres (docker compose)
	docker compose up -d postgres

db-stop:
	docker compose down

migrate: ## apply Alembic migrations
	$(UV) alembic upgrade head

api: ## API with hot reload on :8000
	$(UV) uvicorn app.main:app --reload --port 8000

admin: ## admin UI on :5173
	cd $(ADMIN) && npm run dev

temporal: ## start a local Temporal dev server (:7233, UI :8233)
	docker compose --profile temporal up -d temporal

worker: ## run the Temporal worker
	$(UV) python -m app.temporal.worker

test: test-api test-admin ## all tests

test-api:
	$(UV) pytest -v

test-admin:
	cd $(ADMIN) && npm test

lint: ## ruff + eslint + tsc
	$(UV) ruff check . && $(UV) ruff format --check .
	cd $(ADMIN) && npm run lint && npx tsc -b

format:
	$(UV) ruff format . && $(UV) ruff check . --fix

check: lint test eval ## the CI gate
	cd $(ADMIN) && npm run build

eval: ## offline routing eval (fails below threshold)
	$(UV) python evals/run_evals.py

eval-promptfoo: ## Promptfoo routing eval against a running API
	cd $(API) && npx --yes promptfoo@latest eval -c evals/promptfoo.routing.yaml

clean:
	rm -rf $(API)/.pytest_cache $(API)/.ruff_cache $(API)/*.db $(ADMIN)/dist
