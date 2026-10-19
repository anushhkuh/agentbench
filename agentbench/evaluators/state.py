from agentbench.models import Score
from .output import equal


class StateEvaluator:
    def evaluate(self, run, scenario, final_state):
        checks = []
        for assertion in scenario.expected.state:
            path = assertion.path
            actual = final_state
            try:
                for key in path:
                    actual = actual[key]
                if assertion.op == "equals":
                    passed = equal(actual, assertion.value)
                elif assertion.op == "length":
                    passed = isinstance(actual, (list, dict, str)) and len(actual) == assertion.value
                else:
                    if not isinstance(actual, list):
                        raise TypeError("unique requires a list")
                    values = [item[assertion.value] for item in actual] if assertion.value is not None else actual
                    passed = all(not equal(value, previous) for i, value in enumerate(values) for previous in values[:i])
                reason = "matched" if passed else "assertion failed"
            except (KeyError, IndexError, TypeError):
                passed, reason = False, "missing path or incompatible state type"
            checks.append({"path": path, "op": assertion.op, "expected": assertion.value,
                           "actual": actual, "passed": passed, "reason": reason})
        failed = [f"{c['path']} {c['op']}: {c['reason']}" for c in checks if not c["passed"]]
        return Score(evaluator="state", passed=not failed,
                     reason="; ".join(failed) or "state assertions satisfied", evidence={"checks": checks})
