import json
from agentbench.models import Score


def equal(actual, expected):
    # JSON equality must not conflate booleans and integers (True == 1 in Python).
    return json.dumps(actual, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False)


class OutputEvaluator:
    def evaluate(self, run, scenario, final_state):
        expected = scenario.expected
        failures = []
        if expected.check_output and not equal(run.output, expected.output):
            failures.append("output does not exactly match expected value")
        for key, value in expected.output_fields.items():
            if not isinstance(run.output, dict) or key not in run.output or not equal(run.output[key], value):
                failures.append(f"output field {key!r} mismatch or missing")
        return Score(evaluator="output", passed=not failures,
                     reason="; ".join(failures) or "output assertions satisfied",
                     evidence={"actual": run.output, "expected": expected.model_dump(exclude_unset=True, include={"output", "output_fields"})})
