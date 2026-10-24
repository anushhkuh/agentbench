import json
from pathlib import Path
import pytest
from typer.testing import CliRunner
from agentbench.cli import app

DATASET = Path(__file__).parents[1] / "datasets/refunds.yaml"


@pytest.fixture
def reports(tmp_path):
    paths = []
    for name, expected_exit in [("scripted_agent", 0), ("flawed_agent", 1)]:
        path = tmp_path / f"{name}.json"
        result = CliRunner().invoke(app, ["eval", "--agent", f"examples.support_agent:{name}",
            "--dataset", str(DATASET), "--out", str(path)])
        assert result.exit_code == expected_exit, result.output
        paths.append(str(path))
    return paths


def test_compare_gate_exit_codes_and_overrides(reports, tmp_path):
    good, bad = reports
    args = ["compare", "--baseline", good, "--candidate"]
    assert CliRunner().invoke(app, args + [good]).exit_code == 0
    result = CliRunner().invoke(app, args + [bad, "--out", str(tmp_path / "comparison.json")])
    assert result.exit_code == 1, result.output
    assert "refund_above_limit" in result.output
    assert len(json.loads((tmp_path / "comparison.json").read_text())["regressions"]) == 7
    config = tmp_path / "thresholds.json"
    config.write_text(json.dumps({"min_pass_rate": .65, "max_pass_rate_drop": .35, "max_case_regressions": 7}))
    assert CliRunner().invoke(app, args + [bad, "--thresholds", str(config)]).exit_code == 0
    assert CliRunner().invoke(app, args + [bad, "--thresholds", str(config), "--min-pass-rate", "1"]).exit_code == 1


def test_trace_explains_blocked_action(reports):
    result = CliRunner().invoke(app, ["trace", "--run", reports[1], "--scenario", "refund_above_limit"])
    assert result.exit_code == 0, result.output
    assert "issue_refund" in result.output and "manager approval required" in result.output
    assert "forbidden" in result.output and "parent=" in result.output
    missing = CliRunner().invoke(app, ["trace", "--run", reports[1], "--scenario", "missing"])
    assert missing.exit_code == 2


@pytest.mark.parametrize("change", ["hash", "version", "malformed", "empty", "missing_key"])
def test_invalid_report_exits_two(reports, tmp_path, change):
    report = json.loads(Path(reports[0]).read_text())
    if change == "hash":
        report["experiment"]["dataset_hash"] = "different"
    elif change == "version":
        report["schema_version"] = "1.0"
    elif change == "empty":
        report["runs"] = []
    elif change == "missing_key":
        del report["experiment"]
    path = tmp_path / "invalid.json"
    path.write_text("{" if change == "malformed" else json.dumps(report))
    result = CliRunner().invoke(app, ["compare", "--baseline", reports[0], "--candidate", str(path)])
    assert result.exit_code == 2, result.output
