import json
from pathlib import Path
from typer.testing import CliRunner
from agentbench.cli import app
from agentbench.models import Expectations
from agentbench.storage import redact

DATASET = Path(__file__).parents[1] / "datasets/refunds.yaml"


def test_redaction_including_error_echoes_and_personal_data():
    value = {"apiKey": "very-secret", "API_KEY": "uppercase-secret", "nested": [{"email": "alice@example.com"}],
             "error": "very-secret was invalid for alice@example.com", "note": "Bearer abc123"}
    result = json.dumps(redact(value))
    assert "very-secret" not in result and "alice@example.com" not in result and "abc123" not in result
    assert "uppercase-secret" not in result
    assert value["apiKey"] == "very-secret"


def test_expectation_roundtrip_does_not_add_null_assertion():
    expected = Expectations()
    assert not Expectations.model_validate(expected.model_dump()).check_output


def test_cli_baseline_json_and_markdown(tmp_path):
    output = tmp_path / "baseline.json"
    result = CliRunner().invoke(app, ["eval", "--agent", "examples.support_agent:scripted_agent",
        "--dataset", str(DATASET), "--out", str(output)])
    assert result.exit_code == 0, result.output
    report = json.loads(output.read_text())
    assert report["summary"]["passed"] == 20
    assert report["summary"]["cost"] is None
    assert len(report["experiment"]["dataset_hash"]) == 64
    assert all(r["passed"] for r in report["runs"])
    assert output.with_suffix(".md").is_file()


def test_cli_failure_has_diagnostics_and_nonzero_exit(tmp_path):
    result = CliRunner().invoke(app, ["eval", "--agent", "examples.support_agent:scripted_agent",
        "--dataset", str(DATASET), "--out", str(tmp_path), "--max-steps", "1"])
    assert result.exit_code == 1
    assert "FAIL" in result.output
    report = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert report["summary"]["failed"] > 0
    assert any(r["status"] == "step_limit" for r in report["runs"])


def test_cli_bad_import_and_settings(tmp_path):
    base = ["eval", "--dataset", str(DATASET), "--out", str(tmp_path)]
    assert CliRunner().invoke(app, base + ["--agent", "not_a_module:agent"]).exit_code == 2
    assert CliRunner().invoke(app, base + ["--agent", "examples.support_agent:scripted_agent", "--settings", "[]"]).exit_code == 2
