from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize("agent,code", [("scripted_agent", 0), ("flawed_agent", 1)])
def test_real_ci_command(agent, code, tmp_path):
    script = Path(__file__).parents[1] / "scripts/ci_gate.py"
    result = subprocess.run([sys.executable, str(script), "--agent", f"examples.support_agent:{agent}",
                             "--out", str(tmp_path)], capture_output=True, text=True, timeout=30)
    assert result.returncode == code, result.stdout + result.stderr
    assert (tmp_path / "candidate.json").is_file()
    assert (tmp_path / "comparison.json").is_file()
