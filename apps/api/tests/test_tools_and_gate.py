from app.agents.rate_limit import RateLimitConfig, RateLimiter
from app.agents.runtime.gate import WRITE_BLOCKED, execute_gated
from app.agents.tools import ToolRegistry, _build_schema
from app.agents.types import OperationType


def test_schema_is_derived_from_the_signature():
    def f(ref: str, count: int, changes: dict, note: str | None = None) -> None: ...

    schema = _build_schema(f)
    assert schema["properties"] == {
        "ref": {"type": "string"},
        "count": {"type": "integer"},
        "changes": {"type": "object"},
        "note": {"type": "string"},
    }
    assert schema["required"] == ["ref", "count", "changes"]


def test_read_sessions_are_never_offered_write_tools():
    read = {t.name for t in ToolRegistry.get_scoped_tools("booking", OperationType.READ)}
    write = {t.name for t in ToolRegistry.get_scoped_tools("booking", OperationType.WRITE)}
    assert read == {"booking_status"}
    assert {"booking_create", "booking_amend", "booking_cancel"} <= write
    assert not {t.name for t in ToolRegistry.get_scoped_tools("tracking", OperationType.WRITE)} & write - read


async def test_gate_blocks_writes_without_permission():
    call = await execute_gated("booking_cancel", {"booking_ref": "BK-100001"}, write_allowed=False)
    assert call.error == WRITE_BLOCKED


async def test_gate_runs_writes_with_permission():
    call = await execute_gated("booking_cancel", {"booking_ref": "BK-100001"}, write_allowed=True)
    assert call.error is None
    assert call.result["status"] == "cancelled"


async def test_gate_reports_unknown_tools():
    call = await execute_gated("nope", {}, write_allowed=True)
    assert "Unknown tool" in call.error


def test_rate_limiter_window():
    limiter = RateLimiter({"t": RateLimitConfig(max_requests=2, window_seconds=60)})
    assert limiter.check("t", "a").allowed
    assert limiter.check("t", "a").allowed
    blocked = limiter.check("t", "a")
    assert not blocked.allowed and blocked.retry_after_seconds > 0
    assert limiter.check("t", "b").allowed  # per caller
    assert limiter.check("other", "a").allowed  # unlimited tool
