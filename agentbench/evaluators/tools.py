from collections import Counter
from agentbench.models import Score


class ToolEvaluator:
    def evaluate(self, run, scenario, final_state):
        counts = Counter(call.name for call in run.calls)
        expected = scenario.expected
        failures = []
        for name in expected.required_tools:
            if not counts[name]:
                failures.append(f"required tool {name!r} was not called")
        for name in expected.forbidden_tools:
            if counts[name]:
                failures.append(f"forbidden tool {name!r} attempted {counts[name]} time(s)")
        for name, maximum in expected.max_calls.items():
            if counts[name] > maximum:
                failures.append(f"tool {name!r} called {counts[name]} times; maximum {maximum}")
        return Score(evaluator="tools", passed=not failures,
                     reason="; ".join(failures) or "tool assertions satisfied",
                     evidence={"attempt_counts": dict(counts)})
