from copy import deepcopy
from pathlib import Path
import yaml
import pytest
from agentbench.models import Dataset
from agentbench.context import AgentContext
from examples.support_agent import scripted_agent
from examples.support_agent.tools import support_tools

DATASET = Dataset.model_validate(yaml.safe_load((Path(__file__).parents[1] / "datasets/refunds.yaml").read_text()))


def test_twenty_cases():
    assert len(DATASET.scenarios) == 20


@pytest.mark.parametrize("case", DATASET.scenarios, ids=lambda case: case.id)
async def test_reference_scenario(case):
    context = AgentContext(deepcopy(case.initial_state), support_tools)
    response = await scripted_agent(case.input, context)
    assert response.output == case.expected.output
    assert context.state == case.expected.state[0].value
    names = [call.name for call in context.calls]
    assert set(case.expected.required_tools) <= set(names)
    assert not set(case.expected.forbidden_tools) & set(names)
