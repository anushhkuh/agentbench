from typing import Protocol

from agentbench.models import EvaluationRun, Scenario, Score
from .output import OutputEvaluator
from .tools import ToolEvaluator
from .state import StateEvaluator


class Evaluator(Protocol):
    def evaluate(self, run: EvaluationRun, scenario: Scenario, final_state: dict) -> Score: ...


def default_evaluators():
    return [OutputEvaluator(), ToolEvaluator(), StateEvaluator()]
