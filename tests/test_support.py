from copy import deepcopy
import pytest
from agentbench.context import AgentContext
from examples.support_agent import scripted_agent
from examples.support_agent.tools import support_tools, ToolError


def state(amount=5000):
    return {"orders": {"o1": {"amount_cents": amount, "eligible": True}},
            "policy": {"automatic_limit_cents": 10000}, "refunds": [], "approvals": []}


async def test_refund_is_idempotent_and_returns_copy():
    env = state()
    tool = support_tools(env)["issue_refund"]
    result = await tool("o1", 5000)
    result["amount_cents"] = 0
    await tool("o1", 5000)
    assert env["refunds"] == [{"order_id": "o1", "amount_cents": 5000}]


@pytest.mark.parametrize("amount", [0, -1, 5001, True, 5000.0])
async def test_invalid_amount_blocked(amount):
    with pytest.raises(ToolError):
        await support_tools(state())["issue_refund"]("o1", amount)


async def test_above_limit_attempt_recorded_but_blocked():
    context = AgentContext(state(15000), support_tools)
    with pytest.raises(ToolError, match="approval"):
        await context.call("issue_refund", order_id="o1", amount=15000)
    assert context.calls[0].error
    assert context.state["refunds"] == []


async def test_agent_obeys_threshold():
    context = AgentContext(state(15000), support_tools)
    result = await scripted_agent({"order_id": "o1"}, context)
    assert result.output == {"status": "approval_requested"}
    assert context.state["refunds"] == []
    assert len(context.state["approvals"]) == 1
