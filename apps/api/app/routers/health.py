from __future__ import annotations

from fastapi import APIRouter

from app.config import VERSION, settings

router = APIRouter(tags=["platform"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": VERSION}


@router.get("/api/config")
async def runtime_config() -> dict:
    return {
        "version": VERSION,
        "auth_mode": settings.auth_mode,
        "write_mode": settings.write_mode,
        "agent_runtime": settings.agent_runtime,
        "llm_provider": settings.llm_provider,
        "case_source": settings.case_source,
        "memory_backend": settings.memory_backend,
        "temporal_enabled": settings.temporal_enabled,
        "langfuse_enabled": settings.langfuse_enabled,
    }
