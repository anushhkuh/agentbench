from copy import deepcopy
import json
from pathlib import Path
import pytest

from agentbench.comparison import Thresholds, compare_reports
from agentbench.datasets import load_dataset
from agentbench.evaluators import default_evaluators
from agentbench.experiments import load_report, summarize
from agentbench.models import AgentResponse, EvaluationRun
from agentbench.reporting import make_report
from agentbench.runner import RunnerConfig, run_dataset
from examples.support_agent import scripted_agent, flawed_agent
from examples.support_agent.tools import support_tools


@pytest.fixture
async def reports():
    dataset = load_dataset(Path(__file__).parents[1] / "datasets/refunds.yaml")
    reports = []
    for agent in [scripted_agent, flawed_agent]:
        runs = await run_dataset(dataset, agent, support_tools, evaluators=default_evaluators())
        reports.append(make_report(dataset, runs, agent.__name__, "support_tools", RunnerConfig(), {}))
    return reports


async def test_regression_and_baseline_gate(reports):
    baseline, candidate = reports
    assert compare_reports(baseline, baseline)["passed"]
    result = compare_reports(baseline, candidate)
    assert not result["passed"]
    assert len(result["regressions"]) == 7
    assert candidate["summary"]["passed"] == 13
    assert result["per_scenario"]
    assert compare_reports(baseline, candidate, Thresholds(min_pass_rate=.65, max_pass_rate_drop=.35, max_case_regressions=7))["passed"]
    for before, after in zip(baseline["runs"], candidate["runs"]):
        assert before["output"] == after["output"]
        assert before["final_state"] == after["final_state"]


@pytest.mark.parametrize("key,value", [
    ("dataset_hash", "other"), ("dataset_version", "2"), ("evaluators", {"output": "2"}),
    ("runner", {"trials": 2}), ("tool_factory", "other"), ("execution_mode", "stochastic")])
async def test_incompatible_metadata(reports, key, value):
    baseline, candidate = reports
    candidate["experiment"][key] = value
    with pytest.raises(ValueError, match=key):
        compare_reports(baseline, candidate)


async def test_missing_case_rejected(reports):
    baseline, candidate = reports
    candidate["runs"].pop()
    with pytest.raises(ValueError, match="coverage"):
        compare_reports(baseline, candidate)


async def test_report_loader_recomputes_summary_and_rejects_duplicates(reports, tmp_path):
    report = reports[1]
    report["summary"]["pass_rate"] = 1
    for run in report["runs"]:
        run["passed"] = True
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report))
    assert load_report(path)["summary"]["pass_rate"] == .65
    report["runs"].append(report["runs"][0])
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="duplicate"):
        load_report(path)


async def test_latency_threshold(reports):
    baseline = reports[0]
    candidate = deepcopy(baseline)
    candidate["summary"]["latency_p95_ms"] = baseline["summary"]["latency_p95_ms"] * 2
    assert not compare_reports(baseline, candidate, Thresholds(max_p95_increase_pct=50))["passed"]


def test_usage_and_cost_unknown_if_incomplete():
    base = dict(id="r", scenario_id="s", trial=1, status="completed", final_state={}, latency_ms=1)
    runs = [EvaluationRun(**base, usage={"input_tokens": 10}, cost_usd=.01),
            EvaluationRun(**base, usage={"input_tokens": 20}, cost_usd=.02)]
    assert summarize(runs)["usage"] == {"input_tokens": 30}
    assert summarize(runs)["cost"] == pytest.approx(.03)
    runs[1].usage = None
    runs[1].cost_usd = None
    assert summarize(runs)["usage"] is None and summarize(runs)["cost"] is None
    with pytest.raises(ValueError):
        AgentResponse(output="x", usage={"input_tokens": float("nan")})


@pytest.mark.parametrize("value", [-1, 1.1, float("nan")])
def test_invalid_threshold(value):
    with pytest.raises(ValueError):
        Thresholds(min_pass_rate=value)


async def test_loader_rejects_truncated_report(reports, tmp_path):
    report = reports[0]
    report["runs"].pop()
    path = tmp_path / "truncated.json"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="coverage"):
        load_report(path)
