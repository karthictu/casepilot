from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.routers._errors import translate
from app.security import Principal, require_operator
from app.services import case_service

# Case and HITL payloads carry customer contact details: every route needs the operator scope.
router = APIRouter(prefix="/api/cases", tags=["cases"], dependencies=[Depends(require_operator)])


@router.post("/pull")
async def pull(db: AsyncSession = Depends(get_db), principal: Principal = Depends(require_operator)) -> dict:
    return await case_service.pull_cases(db, actor=principal.sub)


@router.get("")
async def list_cases(
    status: str | None = None, limit: int = Query(100, le=500), db: AsyncSession = Depends(get_db)
) -> dict:
    rows, total = await case_service.list_cases(db, status=status, limit=limit)
    return {"items": [c.to_dict() for c in rows], "total": total}


@router.get("/{case_id}")
async def get_case(case_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    return (await translate(case_service.get_case(db, case_id))).to_dict()


@router.post("/{case_id}/process")
async def process(
    case_id: str, db: AsyncSession = Depends(get_db), principal: Principal = Depends(require_operator)
) -> dict:
    if settings.temporal_enabled:
        from app.temporal.client import start_case_workflow

        case = await translate(case_service.get_case(db, case_id))
        await translate(case_service.ensure_processable(db, case))
        workflow_id = await start_case_workflow(case_id, actor=principal.sub)
        return {"case": case.to_dict(), "workflow_id": workflow_id}
    case, result = await translate(case_service.process(db, case_id, actor=principal.sub))
    return {"case": case.to_dict(), "result": result.to_dict()}
