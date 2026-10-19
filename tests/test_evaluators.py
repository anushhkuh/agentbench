from copy import deepcopy
from pathlib import Path
import pytest
from agentbench.datasets import load_dataset
from agentbench.evaluators import default_evaluators, OutputEvaluator, ToolEvaluator, StateEvaluator
from agentbench.models import EvaluationRun, Scenario, ToolCall
from agentbench.runner import run_dataset
from examples.support_agent import scripted_agent
from examples.support_agent.tools import support_tools, ToolError


def run(output=None, calls=None):
    return EvaluationRun(id="r", scenario_id="s", trial=1, status="completed",
                         output=output, calls=calls or [], final_state={}, latency_ms=1)


def case(expected):
    return Scenario(id="s", input={}, initial_state={}, expected=expected)


@pytest.mark.parametrize("actual,expected,passed", [
    ({"status": "ok"}, {"output_fields": {"status": "ok"}}, True),
    ({}, {"output_fields": {"status": None}}, False),
    (True, {"output": 1}, False),
    (None, {"output": None}, True),
    ("ok", {"output": None}, False),
    ("anything", {}, True),
])
def test_output(actual, expected, passed):
    assert OutputEvaluator().evaluate(run(actual), case(expected), {}).passed == passed


def test_attempts_count_even_when_tool_failed():
    calls = [ToolCall(name="refund", arguments={}, error="blocked") for _ in range(2)]
    score = ToolEvaluator().evaluate(run(calls=calls), case({"forbidden_tools": ["refund"],
        "required_tools": ["approval"], "max_calls": {"refund": 1}}), {})
    assert not score.passed
    assert "forbidden" in score.reason and "required" in score.reason and "maximum" in score.reason


@pytest.mark.parametrize("assertion,state,passed", [
    ({"path": ["missing"], "value": None}, {}, False),
    ({"path": ["refunds"], "op": "length", "value": 1}, {"refunds": []}, False),
    ({"path": ["refunds"], "op": "unique", "value": "order_id"},
     {"refunds": [{"order_id": "o1"}, {"order_id": "o1"}]}, False),
    ({"path": ["refunds"], "op": "unique", "value": "order_id"}, {"refunds": []}, True),
    ({"path": ["a", 0, "b"], "value": 3}, {"a": [{"b": 3}]}, True),
])
def test_state(assertion, state, passed):
    assert StateEvaluator().evaluate(run(), case({"state": [assertion]}), state).passed == passed


async def test_complete_baseline_and_blocked_unsafe_agent():
    data = load_dataset(Path(__file__).parents[1] / "datasets/refunds.yaml")
    runs = await run_dataset(data, scripted_agent, support_tools, evaluators=default_evaluators())
    assert len(runs) == 20 and all(r.passed for r in runs)
    data.scenarios = [next(c for c in data.scenarios if c.id == "refund_above_limit")]

    async def unsafe(input, ctx):
        try:
            await ctx.call("issue_refund", order_id="o1", amount=15000)
        except ToolError:
            pass
        return await scripted_agent(input, ctx)

    bad = (await run_dataset(data, unsafe, support_tools, evaluators=default_evaluators()))[0]
    assert bad.output == {"status": "approval_requested"}
    assert bad.final_state["refunds"] == []
    assert not bad.passed
    assert any(s.evaluator == "tools" and not s.passed for s in bad.scores)


async def test_evaluator_error_is_failure_not_experiment_crash():
    class Broken:
        def evaluate(self, *args):
            raise ValueError("bad evaluator")

    data = load_dataset(Path(__file__).parents[1] / "datasets/refunds.yaml")
    runs = await run_dataset(data, scripted_agent, support_tools, evaluators=[Broken()])
    assert len(runs) == 20
    assert all(not r.passed and "evaluator error" in r.scores[-1].reason for r in runs)
