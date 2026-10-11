async def _pull_and_find(client, external_id: str) -> dict:
    assert (await client.post("/api/cases/pull")).json() == {"pulled": 8, "created": 8}
    items = (await client.get("/api/cases")).json()["items"]
    return next(c for c in items if c["external_id"] == external_id)


async def test_pull_is_idempotent(client):
    await client.post("/api/cases/pull")
    second = await client.post("/api/cases/pull")
    assert second.json()["created"] == 0
    assert (await client.get("/api/cases")).json()["total"] == 8


async def test_case_to_hitl_to_booked(client):
    case = await _pull_and_find(client, "CASE-0001")

    processed = (await client.post(f"/api/cases/{case['id']}/process")).json()
    assert processed["case"]["status"] == "hitl_required"
    item_id = processed["case"]["hitl_item_id"]

    queue = (await client.get("/api/hitl/queue", params={"status": "pending"})).json()["items"]
    assert [i["id"] for i in queue] == [item_id]
    assert queue[0]["action"] == "booking_create"

    reviewed = (
        await client.post(f"/api/hitl/queue/{item_id}/review", json={"decision": "approve", "note": "ok"})
    ).json()
    assert reviewed["status"] == "executed"
    assert reviewed["result"]["result"]["booking_ref"].startswith("BK-")

    final = (await client.get(f"/api/cases/{case['id']}")).json()
    assert final["status"] == "booked"
    assert final["booking_ref"] == reviewed["result"]["result"]["booking_ref"]

    events = [e["event_type"] for e in (await client.get("/api/audit")).json()["items"]]
    for expected in (
        "cases.pulled",
        "hitl.submitted",
        "case.hitl_required",
        "hitl.approved",
        "hitl.executed",
        "case.booked",
    ):
        assert expected in events


async def test_reject_marks_the_case_rejected(client):
    case = await _pull_and_find(client, "CASE-0004")
    item_id = (await client.post(f"/api/cases/{case['id']}/process")).json()["case"]["hitl_item_id"]
    reviewed = (await client.post(f"/api/hitl/queue/{item_id}/review", json={"decision": "reject"})).json()
    assert reviewed["status"] == "rejected"
    assert (await client.get(f"/api/cases/{case['id']}")).json()["status"] == "rejected"


async def test_manual_review_needs_operator_supplied_call(client):
    case = await _pull_and_find(client, "CASE-0002")  # missing cargo-ready date
    item_id = (await client.post(f"/api/cases/{case['id']}/process")).json()["case"]["hitl_item_id"]
    bare = await client.post(f"/api/hitl/queue/{item_id}/review", json={"decision": "approve"})
    assert bare.status_code == 422

    fixed = await client.post(
        f"/api/hitl/queue/{item_id}/review",
        json={
            "decision": "approve",
            "tool": "booking_create",
            "arguments": {
                "origin": "Shanghai",
                "destination": "Los Angeles",
                "container_type": "20GP",
                "container_count": 3,
                "cargo_ready_date": "2026-11-20",
            },
        },
    )
    assert fixed.json()["status"] == "executed"
    assert fixed.json()["payload"]["original"]["tool"] is None


async def test_skipped_case_and_double_processing(client):
    tracking = await _pull_and_find(client, "CASE-0005")
    skipped = (await client.post(f"/api/cases/{tracking['id']}/process")).json()["case"]
    assert skipped["status"] == "skipped" and skipped["intent"] is None and skipped["confidence"] is None

    case = next(c for c in (await client.get("/api/cases")).json()["items"] if c["external_id"] == "CASE-0001")
    await client.post(f"/api/cases/{case['id']}/process")
    assert (await client.post(f"/api/cases/{case['id']}/process")).status_code == 409


async def test_audit_payload_is_pii_redacted(client):
    await _pull_and_find(client, "CASE-0001")
    case = next(c for c in (await client.get("/api/cases")).json()["items"] if c["external_id"] == "CASE-0008")
    await client.post(f"/api/cases/{case['id']}/process")
    body = (await client.get("/api/audit")).text
    assert "7946" not in body and "@hooli" not in body


async def test_reviewing_twice_conflicts(client):
    case = await _pull_and_find(client, "CASE-0004")
    item_id = (await client.post(f"/api/cases/{case['id']}/process")).json()["case"]["hitl_item_id"]
    await client.post(f"/api/hitl/queue/{item_id}/review", json={"decision": "reject"})
    assert (await client.post(f"/api/hitl/queue/{item_id}/review", json={"decision": "approve"})).status_code == 409


async def test_platform_endpoints(client):
    assert (await client.get("/health")).json()["status"] == "ok"
    config = (await client.get("/api/config")).json()
    assert config["write_mode"] == "shadow" and config["llm_provider"] == "mock"
    agents = {a["agent_id"] for a in (await client.get("/api/agents")).json()["items"]}
    assert agents == {"booking", "tracking"}
    tools = {t["name"]: t for t in (await client.get("/api/tools")).json()["items"]}
    assert tools["booking_create"]["operation_type"] == "write"
    decision = (await client.post("/api/agents/orchestrator/classify", json={"query": "Where is BK-100001?"})).json()
    assert decision["route_to"] == "tracking"


async def test_review_falls_back_inline_when_the_workflow_is_gone(client, db, monkeypatch):
    from app.config import settings
    from app.services import hitl
    from app.temporal import client as temporal_client

    case = await _pull_and_find(client, "CASE-0004")
    item_id = (await client.post(f"/api/cases/{case['id']}/process")).json()["case"]["hitl_item_id"]
    item = await hitl.get(db, item_id)
    item.workflow_id = "case-timed-out"
    await db.commit()

    async def gone(workflow_id, item_id):
        raise RuntimeError("workflow execution already completed")

    monkeypatch.setattr(settings, "temporal_enabled", True)
    monkeypatch.setattr(temporal_client, "signal_review", gone)
    reviewed = await client.post(f"/api/hitl/queue/{item_id}/review", json={"decision": "approve"})
    assert reviewed.status_code == 200 and reviewed.json()["status"] == "executed"
    assert (await client.get(f"/api/cases/{case['id']}")).json()["status"] == "booked"
