from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.agents.orchestrator import run_orchestrator
from app.agents.plugin import registry
from app.agents.tools import ToolRegistry
from app.security import Principal, get_principal

router = APIRouter(prefix="/api", tags=["agents"])


class ClassifyRequest(BaseModel):
    query: str


@router.get("/agents")
async def list_agents() -> dict:
    return {"items": [p.to_dict() for p in registry.list()]}


@router.get("/tools")
async def list_tools() -> dict:
    return {"items": [t.to_dict() for t in ToolRegistry.all()]}


@router.post("/agents/orchestrator/classify")
async def classify(body: ClassifyRequest, principal: Principal = Depends(get_principal)) -> dict:
    decision = await run_orchestrator(body.query, customer_id=principal.sub)
    return {k: v for k, v in decision.items() if not k.startswith("_")}
