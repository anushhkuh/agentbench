import asyncio
import json
import pytest
from agentbench.context import AgentContext
from agentbench.storage import redact


async def test_nested_and_concurrent_spans():
    async def inner():
        await asyncio.sleep(.001)
        return "ok"

    async def outer():
        return await ctx.call("inner")

    ctx = AgentContext({}, lambda state: {"outer": outer, "inner": inner})
    await asyncio.gather(ctx.call("outer"), ctx.call("outer"))
    parents = [c for c in ctx.calls if c.name == "outer"]
    children = [c for c in ctx.calls if c.name == "inner"]
    assert len({c.id for c in ctx.calls}) == 4
    assert {c.parent_id for c in children} == {c.id for c in parents}
    assert all(c.parent_id == ctx.run_id for c in parents)
    for call in ctx.calls:
        assert call.run_id == ctx.run_id
        assert call.status == "success"
        assert call.duration_ms > 0
        assert call.ended_at >= call.started_at
        assert call.started_at.tzinfo is not None


async def test_errors_and_cancellation_close_spans():
    async def bad(api_key):
        raise ValueError(f"invalid {api_key}")

    async def slow():
        await asyncio.sleep(10)

    ctx = AgentContext({}, lambda state: {"bad": bad, "slow": slow})
    with pytest.raises(ValueError):
        await ctx.call("bad", api_key="private-value")
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(ctx.call("slow"), .01)
    assert [c.status for c in ctx.calls] == ["error", "cancelled"]
    assert all(c.ended_at and c.duration_ms >= 0 for c in ctx.calls)
    safe = json.dumps(redact([c.model_dump(mode="json") for c in ctx.calls]))
    assert "private-value" not in safe
    assert all(c.parent_id == ctx.run_id for c in ctx.calls)
