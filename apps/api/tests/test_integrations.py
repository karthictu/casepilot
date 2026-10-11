"""Adapter tests. Optional SDKs are skipped when their extra is not installed."""

import json
import types

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import settings
from app.integrations.case_source.salesforce import SalesforceCaseSource


@pytest.fixture
def sf_settings(monkeypatch, tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path = tmp_path / "key.pem"
    path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    monkeypatch.setattr(settings, "salesforce_client_id", "client")
    monkeypatch.setattr(settings, "salesforce_username", "integration@example.com")
    monkeypatch.setattr(settings, "salesforce_private_key_path", str(path))
    monkeypatch.setattr(settings, "salesforce_case_filter", "Origin = 'Email'")


async def test_salesforce_jwt_bearer_and_soql(sf_settings):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/services/oauth2/token":
            assert b"jwt-bearer" in request.content
            return httpx.Response(200, json={"access_token": "tok", "instance_url": "https://org.example.com"})
        seen["q"] = request.url.params["q"]
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(
            200,
            json={
                "records": [
                    {
                        "Id": "500X1",
                        "Subject": "Book",
                        "Description": "Book 1x20GP",
                        "SuppliedEmail": "a@example.com",
                        "Reason": "Booking Create",
                        "CreatedDate": "2026-10-01T10:00:00.000+0000",
                    }
                ]
            },
        )

    cases = await SalesforceCaseSource(transport=httpx.MockTransport(handler)).fetch_new(limit=5)
    assert cases[0].external_id == "500X1" and cases[0].reason == "booking_create"
    assert "FROM Case WHERE (Origin = 'Email')" in seen["q"] and seen["q"].endswith("LIMIT 5")


async def test_litellm_client_parses_tool_calls(monkeypatch):
    litellm = pytest.importorskip("litellm")
    from app.agents.llm.litellm_client import LiteLLMClient

    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        fn = types.SimpleNamespace(name="booking_status", arguments=json.dumps({"booking_ref": "BK-100001"}))
        message = types.SimpleNamespace(content=None, tool_calls=[types.SimpleNamespace(id="c1", function=fn)])
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=message)],
            model="openai/x",
            usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(settings, "litellm_api_base", "http://proxy.local")
    resp = await LiteLLMClient().complete(
        model="gpt-x",
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "booking_status"}}],
    )
    assert resp.tool_calls[0].arguments == {"booking_ref": "BK-100001"}
    assert resp.input_tokens == 10
    assert captured["model"] == "litellm_proxy/gpt-x" and captured["api_base"] == "http://proxy.local"


async def test_adk_runtime_runs_the_same_flow(monkeypatch):
    pytest.importorskip("google.adk")
    from app.agents.graphs.pipeline import run_pipeline

    monkeypatch.setattr(settings, "agent_runtime", "adk")
    read = await run_pipeline("Where is BK-100001?", customer_id="c1")
    assert read["route_to"] == "tracking" and "Loaded on vessel" in read["response_text"]

    proposal = await run_pipeline("Cancel booking BK-100002", customer_id="c1")
    assert proposal["hitl_required"] and proposal["proposed_call"]["tool"] == "booking_cancel"

    write = await run_pipeline("Cancel booking BK-100002", customer_id="c1", write_allowed=True)
    assert write["decision"]["outcome"] == "executed"
    assert [c["name"] for c in write["tool_calls"]] == ["booking_cancel"]


async def test_adk_runtime_still_gates_writes(monkeypatch):
    pytest.importorskip("google.adk")
    from app.agents.llm import LLMResponse, LLMToolCall, set_llm_client
    from app.agents.runtime.engine import run_agent
    from app.agents.types import AgentConfig, SessionContext
    from app.integrations.booking_backend import get_booking_backend

    class SneakyWriter:  # calls a write tool that was never offered to a read-only session
        async def complete(self, **kwargs):
            return LLMResponse(
                tool_calls=[LLMToolCall(id="w", name="booking_cancel", arguments={"booking_ref": "BK-100001"})]
            )

    monkeypatch.setattr(settings, "agent_runtime", "adk")
    set_llm_client(SneakyWriter())
    try:
        result = await run_agent(
            AgentConfig(name="booking", model="m", system_prompt="p", max_turns=2),
            [{"role": "user", "content": "x"}],
            SessionContext(write_allowed=False),
        )
    finally:
        set_llm_client(None)
    assert not any(tc.name == "booking_cancel" and tc.error is None for tc in result.tool_calls)
    assert (await get_booking_backend().get("BK-100001"))["status"] == "confirmed"


def test_langfuse_tracer_builds_spans(monkeypatch):
    pytest.importorskip("langfuse")
    from app.observability.langfuse_tracer import LangfuseTracer

    monkeypatch.setattr(settings, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-test")
    monkeypatch.setattr(settings, "langfuse_host", "http://127.0.0.1:9")  # nothing listening: export just fails
    tracer = LangfuseTracer()
    with tracer.span("unit", input={"a": 1}) as span:
        span.update(output={"b": 2})


def test_mem0_store_is_importable():
    pytest.importorskip("mem0")
    from app.agents.memory.mem0_store import Mem0Store

    assert hasattr(Mem0Store, "search")
