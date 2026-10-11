import json


async def test_agent_card_lists_registered_agents(client):
    card = (await client.get("/.well-known/agent.json")).json()
    assert {s["id"] for s in card["skills"]} == {"booking", "tracking"}
    assert card["url"].endswith("/a2a")


def _send(text: str) -> dict:
    return {"message": {"role": "user", "parts": [{"type": "text", "text": text}]}}


async def test_a2a_read_completes(client):
    task = (await client.post("/a2a/tasks/send", json=_send("Where is BK-100001?"))).json()
    assert task["status"]["state"] == "completed"
    assert "BK-100001" in task["artifacts"][0]["parts"][0]["text"]


async def test_a2a_write_waits_for_operator_then_completes(client):
    task = (await client.post("/a2a/tasks/send", json=_send("Cancel booking BK-100002"))).json()
    assert task["status"]["state"] == "input-required"
    item_id = task["metadata"]["hitl_item_id"]
    await client.post(f"/api/hitl/queue/{item_id}/review", json={"decision": "approve"})
    later = (await client.get(f"/a2a/tasks/{task['id']}")).json()
    assert later["status"]["state"] == "completed"
    assert "BK-100002" in later["artifacts"][0]["parts"][0]["text"]


async def _rpc(client, method: str, params: dict | None = None, rid: int = 1) -> dict:
    return (await client.post("/mcp", json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params})).json()


async def test_mcp_initialize_and_list(client):
    init = await _rpc(client, "initialize", {})
    assert init["result"]["serverInfo"]["name"] == "casepilot"
    tools = {t["name"]: t for t in (await _rpc(client, "tools/list"))["result"]["tools"]}
    assert tools["booking_status"]["annotations"]["readOnlyHint"] is True
    assert "booking_create" in tools


async def test_mcp_read_tool_runs(client):
    res = await _rpc(client, "tools/call", {"name": "booking_status", "arguments": {"booking_ref": "BK-100001"}})
    assert json.loads(res["result"]["content"][0]["text"])["status"] == "confirmed"


async def test_mcp_write_tool_becomes_hitl(client):
    res = await _rpc(client, "tools/call", {"name": "booking_cancel", "arguments": {"booking_ref": "BK-100001"}})
    body = json.loads(res["result"]["content"][0]["text"])
    assert body["status"] == "pending_approval"
    item = (await client.get(f"/api/hitl/queue/{body['hitl_item_id']}")).json()
    assert item["source"] == "mcp" and item["action"] == "booking_cancel"
    status = await _rpc(client, "tools/call", {"name": "booking_status", "arguments": {"booking_ref": "BK-100001"}})
    assert json.loads(status["result"]["content"][0]["text"])["status"] == "confirmed"  # not cancelled yet


async def test_mcp_unknown_method_and_notification(client):
    assert (await _rpc(client, "nope"))["error"]["code"] == -32601
    note = await client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert note.status_code == 202


def _events(body: str) -> list[dict]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


async def test_agui_streams_tool_calls_and_text(client):
    resp = await client.post(
        "/api/agui",
        json={
            "threadId": "t1",
            "runId": "r1",
            "messages": [{"id": "m1", "role": "user", "content": "Where is BK-100001?"}],
        },
    )
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _events(resp.text)
    types = [e["type"] for e in events]
    assert types[0] == "RUN_STARTED" and types[-1] == "RUN_FINISHED"
    assert "TOOL_CALL_START" in types
    text = "".join(e["delta"] for e in events if e["type"] == "TEXT_MESSAGE_CONTENT")
    assert "Loaded on vessel" in text


async def test_agui_emits_hitl_event_for_writes(client):
    resp = await client.post(
        "/api/agui", json={"messages": [{"id": "m1", "role": "user", "content": "Cancel booking BK-100003"}]}
    )
    hitl = [e for e in _events(resp.text) if e["type"] == "CUSTOM" and e["name"] == "hitl"]
    assert hitl and hitl[0]["value"]["action"] == "booking_cancel"


async def test_a2a_task_is_only_visible_to_its_owner(client, monkeypatch):
    import jwt

    from app.config import settings

    task = (await client.post("/a2a/tasks/send", json=_send("Where is BK-100001?"))).json()
    monkeypatch.setattr(settings, "auth_mode", "jwt")
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-test-secret-test-secret")
    other = jwt.encode({"sub": "someone-else", "scope": "tracking.read"}, settings.jwt_secret, algorithm="HS256")
    resp = await client.get(f"/a2a/tasks/{task['id']}", headers={"Authorization": f"Bearer {other}"})
    assert resp.status_code == 404


async def test_mcp_read_calls_are_audited(client):
    await _rpc(client, "tools/call", {"name": "booking_status", "arguments": {"booking_ref": "BK-100001"}})
    events = [e["event_type"] for e in (await client.get("/api/audit")).json()["items"]]
    assert "mcp.tool_call" in events
