from datetime import datetime, timezone
from uuid import uuid4
from .datasets import dataset_hash
from .experiments import code_revision, summarize, percentile


def make_report(dataset, runs, agent, tools, config, settings, *, execution_mode="deterministic", model_id=None, prompt_id=None):
    return {
        "schema_version": "1.1",
        "experiment": {"id": str(uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
                       "agent": agent, "tool_factory": tools, "settings": settings,
                       "runner": config.model_dump(), "dataset_version": dataset.version,
                       "dataset_hash": dataset_hash(dataset),
                       "scenario_ids": [scenario.id for scenario in dataset.scenarios],
                       "code": code_revision(), "execution_mode": execution_mode,
                       "model_id": model_id, "prompt_id": prompt_id,
                       "evaluators": {"execution": "1", "output": "1", "tools": "1", "state": "1"}},
        "summary": summarize(runs),
        "runs": [{**run.model_dump(mode="json"), "passed": run.passed} for run in runs],
    }


def markdown_report(report):
    summary = report["summary"]
    lines = ["# AgentBench benchmark", "", f"Passed: {summary['passed']}/{summary['total']}", "",
             f"Dataset hash: `{report['experiment']['dataset_hash']}`", "",
             f"Mode: {report['experiment']['execution_mode']}", "",
             f"Usage: {summary['usage'] if summary['usage'] is not None else 'unknown'}; cost (USD): {summary['cost'] if summary['cost'] is not None else 'unknown'}.", "",
             "| Scenario | Trial | Result | Diagnostics |", "|---|---:|---|---|"]
    for run in report["runs"]:
        reasons = "; ".join(s["reason"] for s in run["scores"] if not s["passed"])
        reasons = reasons.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {run['scenario_id']} | {run['trial']} | {'PASS' if run['passed'] else 'FAIL'} | {reasons} |")
    return "\n".join(lines) + "\n"
