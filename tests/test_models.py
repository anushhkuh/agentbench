import pytest
from pydantic import ValidationError
from agentbench.models import Dataset, Expectations, Scenario


def test_duplicate_ids_rejected():
    case = Scenario(id="same", input={}, initial_state={}, expected=Expectations())
    with pytest.raises(ValidationError, match="unique"):
        Dataset(version="1", scenarios=[case, case])


def test_negative_call_limit_rejected():
    with pytest.raises(ValidationError):
        Expectations(max_calls={"refund": -1})
