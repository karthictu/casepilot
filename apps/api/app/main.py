"""casepilot API: one processing core behind four ingress surfaces.

case-driven  /api/cases/*        CRM case → classify → extract → book (shadow-first)
A2A          /a2a, /.well-known  external agents
MCP          /mcp                external agents' tool calls (scope-filtered; writes → HITL)
chat         /api/agui           AG-UI over SSE for the admin chat
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.plugin import load_plugins
from app.config import VERSION, settings
from app.middleware import RequestIdMiddleware
from app.observability.tracer import get_tracer
from app.routers import a2a, agents, agui, audit, cases, health, hitl, mcp

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_plugins()
    if settings.auto_create_tables:
        from app.database import create_all

        await create_all()
    if settings.seed_on_startup:
        from app.database import session_scope
        from app.services.case_service import pull_cases

        async with session_scope() as db:
            await pull_cases(db, actor="startup")
    yield
    get_tracer().flush()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=VERSION, lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (health, agents, cases, hitl, audit, a2a, mcp, agui):
        app.include_router(module.router)
    app.include_router(a2a.well_known_router)
    return app


app = create_app()
