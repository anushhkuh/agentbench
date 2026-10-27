"""Report loading, provenance, and metrics shared by reporting and comparison."""
import json
import math
from pathlib import Path
import subprocess

from .models import EvaluationRun


def code_revision():
    root = Path(__file__).resolve().parents[1]
    command = ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root)]
    try:
        commit = subprocess.run(command + ["rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=5).stdout.strip()
        dirty = bool(subprocess.run(command + ["status", "--porcelain"], capture_output=True, text=True, check=True, timeout=5).stdout.strip())
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "dirty": None}


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summarize(runs):
    if not runs:
        raise ValueError("report must contain runs")
    passed = sum(run.passed for run in runs)
    # A total is known only if every run provides the same metric.
    common = set.intersection(*(set(r.usage or {}) if r.usage_complete else set() for r in runs))
    usage = {key: sum(r.usage[key] for r in runs) for key in sorted(common)} or None
    cost = sum(r.cost_usd for r in runs) if all(r.cost_usd is not None for r in runs) else None
    return {"total": len(runs), "passed": passed, "failed": len(runs) - passed,
            "pass_rate": passed / len(runs),
            "latency_p50_ms": percentile([r.latency_ms for r in runs], .50),
            "latency_p95_ms": percentile([r.latency_ms for r in runs], .95),
            "usage": usage, "cost": cost}


def load_report(path):
    try:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
        if report["schema_version"] != "1.1":
            raise ValueError("expected report schema 1.1; rerun older experiments")
        metadata = report["experiment"]
        for key in ("dataset_hash", "dataset_version", "scenario_ids", "evaluators", "runner", "tool_factory", "execution_mode"):
            if not metadata.get(key):
                raise ValueError(f"missing experiment metadata: {key}")
        runs = [EvaluationRun.model_validate({k: v for k, v in item.items() if k != "passed"}) for item in report["runs"]]
        keys = [(r.scenario_id, r.trial) for r in runs]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate scenario/trial results")
        scenario_ids = metadata["scenario_ids"]
        trials = metadata["runner"]["trials"]
        if not isinstance(scenario_ids, list) or len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("invalid scenario IDs")
        if type(trials) is not int or trials < 1:
            raise ValueError("invalid trial count")
        if set(keys) != {(scenario, trial) for scenario in scenario_ids for trial in range(1, trials + 1)}:
            raise ValueError("incomplete scenario/trial coverage")
        for run in runs:
            if not math.isfinite(run.latency_ms) or run.latency_ms < 0:
                raise ValueError("invalid latency")
            if run.trial < 1:
                raise ValueError("trial must be positive")
            if run.usage and any(not math.isfinite(v) or v < 0 for v in run.usage.values()):
                raise ValueError("invalid usage metric")
        # Never trust a saved summary or the redundant passed flag as gate input.
        report["summary"] = summarize(runs)
        report["runs"] = [{**r.model_dump(mode="json"), "passed": r.passed} for r in runs]
        return report
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"invalid report structure: {exc}") from exc
