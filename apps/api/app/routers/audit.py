from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditEvent
from app.security import require_operator

router = APIRouter(prefix="/api/audit", tags=["audit"], dependencies=[Depends(require_operator)])


@router.get("")
async def list_events(
    limit: int = Query(100, le=1000), event_type: str | None = None, db: AsyncSession = Depends(get_db)
) -> dict:
    q = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    if event_type:
        q = q.where(AuditEvent.event_type == event_type)
    return {"items": [e.to_dict() for e in (await db.execute(q)).scalars()]}
