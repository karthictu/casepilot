"""Runtime settings, read from `CASEPILOT_*` environment variables (or `.env`).

Every external integration has a switch here and is off by default: the out-of-the-box configuration runs the
whole flow offline on mocks (mock LLM, mock case source, in-memory booking/tracking backends, no Temporal).
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CASEPILOT_", env_file=".env", extra="ignore")

    app_name: str = "casepilot"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://casepilot:casepilot@localhost:5432/casepilot"
    # Create tables on startup instead of running Alembic. Handy for SQLite demos; leave off for Postgres.
    auto_create_tables: bool = False
    seed_on_startup: bool = False

    # ── Auth ─────────────────────────────────────────────────────────────────
    # mock: every request is an operator with all scopes. jwt: verify a bearer token (HS256 secret or JWKS URL).
    auth_mode: Literal["mock", "jwt"] = "mock"
    jwt_secret: str | None = None
    jwt_jwks_url: str | None = None
    jwt_audience: str | None = None
    jwt_issuer: str | None = None

    # ── Agent behaviour ──────────────────────────────────────────────────────
    # shadow: case processing never writes; every write becomes a HITL proposal. live: high-confidence writes run.
    write_mode: Literal["shadow", "live"] = "shadow"
    hitl_confidence_threshold: float = 0.85
    # CRM "reason for case" values this platform owns; any other case is skipped and left to the existing team.
    owned_reasons: list[str] = ["booking_create", "booking_amend", "booking_cancel"]
    # Modules that register an AgentPlugin on import. Add yours here to plug in a new specialist agent.
    agent_modules: list[str] = ["app.agents.booking", "app.agents.tracking"]
    max_cost_usd_per_run: float = 0.50

    # ── Agent runtime + LLM ──────────────────────────────────────────────────
    agent_runtime: Literal["native", "adk"] = "native"
    llm_provider: Literal["mock", "litellm"] = "mock"
    # LiteLLM model strings, e.g. "openai/gpt-4o-mini", "bedrock/<model-id>", "azure/<deployment>", "ollama/llama3.1".
    model_intent: str = "openai/gpt-4o-mini"
    model_extraction: str = "openai/gpt-4o-mini"
    model_reasoning: str = "openai/gpt-4o"
    # Optional: route every call through a LiteLLM proxy (OpenAI-compatible) instead of calling providers directly.
    litellm_api_base: str | None = None
    litellm_api_key: str | None = None

    # ── Memory ───────────────────────────────────────────────────────────────
    memory_backend: Literal["inmemory", "mem0"] = "inmemory"
    # JSON passed to mem0 `Memory.from_config(...)`; empty uses mem0's defaults (OpenAI embeddings).
    mem0_config_json: str | None = None

    # ── Case source ──────────────────────────────────────────────────────────
    case_source: Literal["mock", "salesforce"] = "mock"
    salesforce_login_url: str = "https://login.salesforce.com"
    salesforce_client_id: str | None = None
    salesforce_username: str | None = None
    salesforce_private_key_path: str | None = None
    salesforce_api_version: str = "v61.0"
    # Extra SOQL filter appended with AND, e.g. "Origin = 'Email' AND Status = 'New'".
    salesforce_case_filter: str | None = None

    # ── Observability ────────────────────────────────────────────────────────
    langfuse_enabled: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3000"

    # ── Temporal (self-hosted or Temporal Cloud) ─────────────────────────────
    temporal_enabled: bool = False
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "casepilot"
    temporal_api_key: str | None = None  # Temporal Cloud API-key auth (implies TLS)
    temporal_tls: bool = False


settings = Settings()
