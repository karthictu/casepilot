from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers._errors import translate
from app.security import Principal, require_operator
from app.services import hitl

# Case and HITL payloads carry customer contact details: every route needs the operator scope.
router = APIRouter(prefix="/api/hitl", tags=["hitl"], dependencies=[Depends(require_operator)])


class ReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = None
    # Optional corrections applied on approval (required for `manual_review` items).
    tool: str | None = None
    arguments: dict[str, Any] | None = None


@router.get("/queue")
async def list_queue(status: str | None = None, db: AsyncSession = Depends(get_db)) -> dict:
    return {"items": [i.to_dict() for i in await hitl.list_items(db, status=status)]}


@router.get("/queue/{item_id}")
async def get_item(item_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    return (await translate(hitl.get(db, item_id))).to_dict()


@router.post("/queue/{item_id}/review")
async def review(
    item_id: str,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_operator),
) -> dict:
    item = await translate(
        hitl.review(
            db,
            item_id,
            decision=body.decision,
            reviewer=principal.sub,
            note=body.note,
            tool=body.tool,
            arguments=body.arguments,
        )
    )
    return item.to_dict()
