import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
from agentbench.context import AgentContext, StepLimitExceeded
from agentbench.models import Dataset, Scenario, Expectations
from agentbench.runner import RunnerConfig, run_dataset
from agentbench.experiments import summarize
from examples.support_agent.llm_agent import LLMSettings, run_tool_loop, prompt_identifier
from examples.support_agent.tools import support_tools


class NS(SimpleNamespace):
    def model_dump(self, **kwargs):
        return vars(self)


def response(*calls, text='{"status":"refunded"}', usage=True, status="completed"):
    return NS(output=list(calls), output_text=text, status=status,
              usage=NS(input_tokens=10, output_tokens=5, total_tokens=15) if usage else None)


def call(name, **args):
    return NS(type="function_call", name=name, arguments=json.dumps(args), call_id=name + "-id")


class FakeClient:
    def __init__(self, responses):
        self.items = iter(responses)
        self.requests = []
        self.responses = self

    async def create(self, **kwargs):
        self.requests.append(deepcopy(kwargs))
        item = next(self.items)
        if isinstance(item, BaseException):
            raise item
        return item


def state(amount=5000):
    return {"orders": {"o1": {"amount_cents": amount, "eligible": True}},
            "policy": {"automatic_limit_cents": 10000}, "refunds": [], "approvals": []}


async def test_tool_loop_preserves_reasoning_and_records_usage():
    reasoning = NS(type="reasoning", encrypted_content="opaque")
    client = FakeClient([response(reasoning, call("get_order", order_id="o1")),
                         response(call("get_refund_policy")),
                         response(call("issue_refund", order_id="o1", amount=5000)), response()])
    ctx = AgentContext(state(), support_tools)
    result = await run_tool_loop({"order_id": "o1"}, ctx, client, LLMSettings(model="fake"))
    assert result.output == {"status": "refunded"}
    assert result.usage == {"input_tokens": 40, "output_tokens": 20, "total_tokens": 60}
    assert len(ctx.state["refunds"]) == 1
    assert client.requests[1]["input"][1].type == "reasoning"
    assert client.requests[1]["input"][-1]["call_id"] == "get_order-id"
    assert all(not r["store"] and not r["parallel_tool_calls"] for r in client.requests)
    assert all(c.status == "success" for c in ctx.calls)


async def test_tool_denial_is_traced_and_sent_back():
    client = FakeClient([response(call("issue_refund", order_id="o1", amount=15000)),
                         response(text='{"status":"tool_error"}')])
    ctx = AgentContext(state(15000), support_tools)
    await run_tool_loop({}, ctx, client, LLMSettings(model="fake"))
    assert ctx.calls[0].status == "error" and not ctx.state["refunds"]
    assert "manager approval required" in client.requests[1]["input"][-1]["output"]


@pytest.mark.parametrize("item,match", [
    (response(text="refused"), "invalid final"),
    (response(text='{"status":"made_up"}'), "invalid final"),
    (response(status="incomplete"), "did not complete"),
    (response(call("delete_everything")), "unsupported tool"),
    (response(NS(type="function_call", name="get_order", arguments="{", call_id="bad")), "invalid tool arguments"),
])
async def test_invalid_provider_responses_fail(item, match):
    with pytest.raises(RuntimeError, match=match):
        await run_tool_loop({}, AgentContext(state(), support_tools), FakeClient([item]), LLMSettings(model="fake"))


async def test_model_and_tool_limits():
    ctx = AgentContext(state(), support_tools)
    with pytest.raises(StepLimitExceeded, match="model requests"):
        await run_tool_loop({}, ctx, FakeClient([response(call("get_refund_policy"))]), LLMSettings(model="fake", max_model_calls=1))
    ctx = AgentContext(state(), support_tools, max_steps=1)
    with pytest.raises(StepLimitExceeded, match="tool calls"):
        await run_tool_loop({}, ctx, FakeClient([response(call("get_order", order_id="o1"), call("get_refund_policy"))]), LLMSettings(model="fake"))


async def test_provider_failure_preserves_partial_usage_without_claiming_total():
    async def agent(input, ctx):
        return await run_tool_loop(input, ctx, FakeClient([response(call("get_refund_policy")),
            ValueError("DO-NOT-EXPOSE-KEY")]), LLMSettings(model="fake"))
    dataset = Dataset(version="1", scenarios=[Scenario(id="x", input={}, initial_state=state(), expected=Expectations())])
    runs = await run_dataset(dataset, agent, support_tools)
    assert runs[0].status == "error"
    assert "DO-NOT-EXPOSE-KEY" not in runs[0].error
    assert runs[0].usage["total_tokens"] == 15
    assert not runs[0].usage_complete
    assert summarize(runs)["usage"] is None


async def test_missing_usage_stays_unknown():
    ctx = AgentContext(state(), support_tools)
    result = await run_tool_loop({}, ctx, FakeClient([response(usage=False)]), LLMSettings(model="fake"))
    assert result.usage is None and not ctx.usage_complete


async def test_cancellation_propagates():
    ctx = AgentContext(state(), support_tools)
    with pytest.raises(asyncio.CancelledError):
        await run_tool_loop({}, ctx, FakeClient([asyncio.CancelledError()]), LLMSettings(model="fake"))
    assert not ctx.usage_complete


async def test_refunded_status_available_through_tool():
    env = state()
    env["refunds"] = [{"order_id": "o1", "amount_cents": 5000}]
    result = await support_tools(env)["get_order"]("o1")
    assert result["refunded"] is True
    assert "refunded" not in env["orders"]["o1"]


def test_prompts_have_distinct_versioned_ids():
    assert prompt_identifier({"prompt": "policy-v1"}) != prompt_identifier({"prompt": "checklist-v1"})


async def test_oversized_input_never_calls_provider():
    client = FakeClient([])
    with pytest.raises(StepLimitExceeded, match="request size"):
        await run_tool_loop({"text": "x" * 25000}, AgentContext(state(), support_tools), client, LLMSettings(model="fake"))
    assert client.requests == []
