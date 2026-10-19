from datetime import datetime, timezone
from uuid import uuid4
from .datasets import dataset_hash


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def make_report(dataset, runs, agent, tools, config, settings):
    passed = sum(run.passed for run in runs)
    return {
        "schema_version": "1.0",
        "experiment": {"id": str(uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
                       "agent": agent, "tool_factory": tools, "settings": settings,
                       "runner": config.model_dump(), "dataset_version": dataset.version,
                       "dataset_hash": dataset_hash(dataset),
                       "evaluators": {"execution": "1", "output": "1", "tools": "1", "state": "1"}},
        "summary": {"total": len(runs), "passed": passed, "failed": len(runs) - passed,
                    "pass_rate": passed / len(runs),
                    "latency_p50_ms": percentile([r.latency_ms for r in runs], .50),
                    "latency_p95_ms": percentile([r.latency_ms for r in runs], .95),
                    "usage": None, "cost": None},
        "runs": [{**run.model_dump(mode="json"), "passed": run.passed} for run in runs],
    }


def markdown_report(report):
    summary = report["summary"]
    lines = ["# AgentBench benchmark", "", f"Passed: {summary['passed']}/{summary['total']}", "",
             f"Dataset hash: `{report['experiment']['dataset_hash']}`", "",
             "Usage and cost: unknown (provider aggregation is not implemented).", "",
             "| Scenario | Trial | Result | Diagnostics |", "|---|---:|---|---|"]
    for run in report["runs"]:
        reasons = "; ".join(s["reason"] for s in run["scores"] if not s["passed"])
        reasons = reasons.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {run['scenario_id']} | {run['trial']} | {'PASS' if run['passed'] else 'FAIL'} | {reasons} |")
    return "\n".join(lines) + "\n"
