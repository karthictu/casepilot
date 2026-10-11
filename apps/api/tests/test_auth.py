import jwt
import pytest

from app.config import settings


@pytest.fixture
def jwt_mode(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "jwt")
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-test-secret-test-secret")


def _token(scope: str) -> str:
    return jwt.encode({"sub": "agent-1", "scope": scope}, settings.jwt_secret, algorithm="HS256")


async def test_missing_token_is_401(client, jwt_mode):
    assert (await client.post("/api/cases/pull")).status_code == 401


async def test_operator_scope_is_required(client, jwt_mode):
    resp = await client.post("/api/cases/pull", headers={"Authorization": f"Bearer {_token('tracking.read')}"})
    assert resp.status_code == 403


async def test_mcp_tools_list_is_scope_filtered(client, jwt_mode):
    resp = await client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {_token('tracking.read')}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    names = {t["name"] for t in resp.json()["result"]["tools"]}
    assert names == {"tracking_get_milestones", "tracking_get_eta"}


async def test_mcp_call_without_scope_is_forbidden(client, jwt_mode):
    resp = await client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {_token('tracking.read')}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "booking_cancel", "arguments": {"booking_ref": "BK-100001"}},
        },
    )
    assert resp.json()["error"]["code"] == -32003


async def test_case_and_hitl_reads_need_operator_scope(client, jwt_mode):
    headers = {"Authorization": f"Bearer {_token('tracking.read')}"}
    assert (await client.get("/api/cases", headers=headers)).status_code == 403
    assert (await client.get("/api/hitl/queue", headers=headers)).status_code == 403
    operator = {"Authorization": f"Bearer {_token('casepilot.operator')}"}
    assert (await client.get("/api/cases", headers=operator)).status_code == 200
