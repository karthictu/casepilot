import json

from app.agents.graphs.pipeline import run_pipeline
from app.agents.llm import LLMResponse, LLMToolCall, set_llm_client
from app.agents.runtime.engine import run_agent
from app.agents.types import AgentConfig, AgentStatus


async def test_tracking_question_is_answered_directly():
    state = await run_pipeline("Where is BK-100001?", customer_id="c1")
    assert state["route_to"] == "tracking"
    assert not state["hitl_required"]
    assert "Loaded on vessel" in state["response_text"]
    assert [c["name"] for c in state["tool_calls"]] == ["tracking_get_milestones"]


async def test_booking_write_in_read_only_session_becomes_a_proposal():
    state = await run_pipeline("Book 2x40HC from Rotterdam to Singapore, cargo ready 2026-11-15", customer_id="c1")
    assert state["route_to"] == "booking"
    assert state["hitl_required"]
    assert state["proposed_call"]["tool"] == "booking_create"
    assert state["proposed_call"]["arguments"]["container_type"] == "40HC"


async def test_write_permitted_session_executes():
    state = await run_pipeline("Cancel booking BK-100002", customer_id="c1", write_allowed=True)
    assert state["decision"]["outcome"] == "executed"
    assert not state["hitl_required"]


async def test_unclassifiable_request_goes_to_hitl():
    state = await run_pipeline("hello there", customer_id="c1")
    assert state["route_to"] == "hitl" and state["hitl_required"]
    assert "agent_id" not in state


async def test_ambiguous_request_is_low_confidence():
    state = await run_pipeline("Cancel BK-100001 and book a new one from Antwerp to Busan", customer_id="c1")
    assert state["hitl_required"]
    assert state["orchestrator_decision"]["confidence"] < 0.85


async def test_model_claiming_an_unexecuted_write_is_overruled():
    class Liar:
        async def complete(self, **kwargs):
            if kwargs["agent_name"] == "orchestrator":
                return LLMResponse(content=json.dumps({"intent": "cancel_booking", "confidence": 0.95}))
            return LLMResponse(
                content=json.dumps(
                    {"action": "booking_cancel", "outcome": "executed", "confidence": 0.99, "booking_ref": "BK-100001"}
                )
            )

    set_llm_client(Liar())
    try:
        state = await run_pipeline("Cancel BK-100001", customer_id="c1", write_allowed=True)
    finally:
        set_llm_client(None)
    assert state["decision"]["outcome"] == "hitl_required"
    assert state["hitl_required"]


async def test_runtime_stops_a_tool_loop():
    class Looper:
        async def complete(self, **kwargs):
            return LLMResponse(
                tool_calls=[LLMToolCall(id="x", name="booking_status", arguments={"booking_ref": "BK-100001"})]
            )

    set_llm_client(Looper())
    try:
        result = await run_agent(
            AgentConfig(name="booking", model="m", system_prompt="", max_turns=10),
            [{"role": "user", "content": "status?"}],
        )
    finally:
        set_llm_client(None)
    assert result.status == AgentStatus.LOOP_DETECTED


async def test_memory_is_recalled_for_the_customer():
    from app.agents.memory import get_memory

    await run_pipeline(
        "Book 2x40HC from Rotterdam to Singapore, cargo ready 2026-11-15", customer_id="c9", write_allowed=True
    )
    assert await get_memory().search("Rotterdam", user_id="c9")
