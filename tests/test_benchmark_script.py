import json
from pathlib import Path
import subprocess
import sys


def test_repeated_offline_comparison(tmp_path):
    root = Path(__file__).parents[1]
    result = subprocess.run([sys.executable, str(root / "scripts/benchmark.py"), "--trials", "2",
        "--scenario", "refund_above_limit", "--scenario", "refund_valid", "--out", str(tmp_path)],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    baseline = json.loads((tmp_path / "baseline.json").read_text())
    candidate = json.loads((tmp_path / "candidate.json").read_text())
    assert baseline["summary"]["total"] == 4 and baseline["summary"]["passed"] == 4
    assert candidate["summary"]["passed"] == 2
    assert baseline["experiment"]["execution_mode"] == "deterministic"
    assert len(json.loads((tmp_path / "comparison.json").read_text())["regressions"]) == 2
