import asyncio
from copy import deepcopy
import pytest
from agentbench.context import StepLimitExceeded
from agentbench.models import AgentResponse, Dataset, Scenario, Expectations
from agentbench.runner import RunnerConfig, run_dataset


def dataset(count=3):
    return Dataset(version="1", scenarios=[Scenario(id=str(i), input={"id": i},
        initial_state={"values": []}, expected=Expectations()) for i in range(count)])


async def test_state_input_settings_isolation_and_trials():
    data = dataset()
    original = deepcopy(data)
    settings = {"nested": []}

    async def agent(input, ctx):
        assert ctx.state["values"] == []
        assert ctx.settings["nested"] == []
        ctx.state["values"].append(input.pop("id"))
        ctx.settings["nested"].append(1)
        return AgentResponse(output="ok")

    runs = await run_dataset(data, agent, lambda state: {}, config=RunnerConfig(trials=2), settings=settings)
    assert len(runs) == 6
    assert data == original
    assert settings == {"nested": []}
    assert all(run.passed for run in runs)
    assert len({run.id for run in runs}) == 6


async def test_timeout_exception_and_success_survive_together():
    cancelled = asyncio.Event()

    async def agent(input, ctx):
        if input["id"] == 0:
            try:
                await asyncio.sleep(5)
            finally:
                cancelled.set()
        if input["id"] == 1:
            raise RuntimeError("broken agent")
        return AgentResponse(output="ok")

    runs = await run_dataset(dataset(), agent, lambda state: {}, config=RunnerConfig(timeout_seconds=.02))
    assert [r.status for r in runs] == ["timeout", "error", "completed"]
    assert [r.passed for r in runs] == [False, False, True]
    assert cancelled.is_set()


async def test_bounded_concurrency():
    active = peak = 0

    async def agent(input, ctx):
        nonlocal active, peak
        active += 1
        peak = max(active, peak)
        await asyncio.sleep(.01)
        active -= 1
        return AgentResponse(output="ok")

    await run_dataset(dataset(8), agent, lambda state: {}, config=RunnerConfig(concurrency=2))
    assert peak == 2


async def test_swallowed_step_limit_still_fails():
    async def noop():
        return None

    async def agent(input, ctx):
        await ctx.call("noop")
        try:
            await ctx.call("noop")
        except StepLimitExceeded:
            pass
        return AgentResponse(output="ok")

    runs = await run_dataset(dataset(1), agent, lambda state: {"noop": noop}, config=RunnerConfig(max_steps=1))
    assert runs[0].status == "step_limit"
    assert not runs[0].passed


async def test_factory_failure_recorded():
    def factory(state):
        raise RuntimeError("bad environment")

    runs = await run_dataset(dataset(), None, factory)
    assert len(runs) == 3
    assert all(r.status == "error" for r in runs)


@pytest.mark.parametrize("value", [0, -1])
def test_invalid_runner_configuration(value):
    with pytest.raises(ValueError):
        RunnerConfig(concurrency=value)


async def test_agent_timeout_error_is_not_runner_deadline():
    async def agent(input, ctx):
        raise TimeoutError("upstream timeout")

    runs = await run_dataset(dataset(1), agent, lambda state: {})
    assert runs[0].status == "error"
    assert "upstream timeout" in runs[0].error


async def test_suppressed_cancellation_still_marks_timeout():
    async def agent(input, ctx):
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            return AgentResponse(output="pretend success")

    runs = await run_dataset(dataset(1), agent, lambda state: {}, config=RunnerConfig(timeout_seconds=.01))
    assert runs[0].status == "timeout"
    assert not runs[0].passed


async def test_tool_timeout_preserves_attempt_and_partial_state():
    def factory(state):
        async def slow():
            state["values"].append("partial")
            await asyncio.sleep(5)
        return {"slow": slow}

    async def agent(input, ctx):
        await ctx.call("slow")

    runs = await run_dataset(dataset(1), agent, factory, config=RunnerConfig(timeout_seconds=.01))
    assert runs[0].status == "timeout"
    assert runs[0].final_state["values"] == ["partial"]
    assert "CancelledError" in runs[0].calls[0].error
