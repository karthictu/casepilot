"""MCP (Model Context Protocol) server over HTTP, JSON-RPC 2.0: `initialize`, `ping`, `tools/list`, `tools/call`.

- `tools/list` shows only the tools whose OAuth `scope` the caller holds.
- A read tool runs directly (through the gate). A write tool never runs here: it becomes a HITL item and the
  caller gets its id back, so an external agent can request a booking change but only an operator can apply it.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.agents.plugin import load_plugins
from app.agents.runtime.gate import execute_gated
from app.agents.tools import ToolRegistry
from app.agents.types import OperationType
from app.config import VERSION, settings
from app.database import get_db
from app.security import Principal, get_principal
from app.services import hitl

router = APIRouter(prefix="/mcp", tags=["mcp"])

PROTOCOL_VERSION = "2025-06-18"
METHOD_NOT_FOUND, INVALID_PARAMS, FORBIDDEN = -32601, -32602, -32003


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] | None = None


def _result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _text(value: Any, *, is_error: bool = False) -> dict[str, Any]:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def visible_tools(principal: Principal) -> list[dict[str, Any]]:
    load_plugins()
    return [
        {
            "name": t.name,
            "description": t.description,
            "inputSchema": t.parameters,
            "annotations": {"readOnlyHint": t.operation_type == OperationType.READ},
        }
        for t in ToolRegistry.all()
        if t.scope and principal.has_scope(t.scope)
    ]


async def _tools_call(req: JsonRpcRequest, principal: Principal, db: AsyncSession) -> dict[str, Any]:
    params = req.params or {}
    name, arguments = params.get("name"), params.get("arguments") or {}
    tool_def = ToolRegistry.get(name) if isinstance(name, str) else None
    if tool_def is None or not tool_def.scope:
        return _error(req.id, INVALID_PARAMS, f"Unknown tool: {name}")
    if not principal.has_scope(tool_def.scope):
        return _error(req.id, FORBIDDEN, f"Missing scope: {tool_def.scope}")

    if tool_def.operation_type == OperationType.WRITE:
        item = await hitl.submit(
            db,
            source="mcp",
            source_ref=uuid.uuid4().hex,
            agent_id=(tool_def.agent_scopes or ["mcp"])[0],
            action=name,
            payload={"tool": name, "arguments": arguments, "context": {"caller": principal.sub}},
            confidence=1.0,
            reason="Write requested over MCP; operator approval required",
            customer_id=principal.sub,
            actor=principal.sub,
        )
        await db.commit()
        return _result(req.id, _text({"status": "pending_approval", "hitl_item_id": item.id}))

    call = await execute_gated(name, arguments, write_allowed=False, caller=principal.sub)
    await audit.emit(
        db,
        "mcp.tool_call",
        actor=principal.sub,
        surface="mcp",
        payload={"tool": name, "arguments": arguments, "error": call.error},
    )
    await db.commit()
    if call.error:
        return _result(req.id, _text(call.error, is_error=True))
    return _result(req.id, _text(call.result))


@router.post("")
async def mcp_endpoint(
    req: JsonRpcRequest, db: AsyncSession = Depends(get_db), principal: Principal = Depends(get_principal)
) -> Any:
    if req.id is None:  # a notification (e.g. notifications/initialized): no response body
        return Response(status_code=202)
    if req.method == "initialize":
        return _result(
            req.id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": settings.app_name, "version": VERSION},
            },
        )
    if req.method == "ping":
        return _result(req.id, {})
    if req.method == "tools/list":
        return _result(req.id, {"tools": visible_tools(principal)})
    if req.method == "tools/call":
        return await _tools_call(req, principal, db)
    return _error(req.id, METHOD_NOT_FOUND, f"Method not found: {req.method}")
