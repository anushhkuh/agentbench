"""Run the same deterministic regression gate locally and in GitHub Actions."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="examples.support_agent:scripted_agent")
    parser.add_argument("--out", type=Path, default=root / "runs/ci")
    args = parser.parse_args()
    destination = args.out.resolve()
    command = [sys.executable, "-m", "agentbench.cli"]
    result = subprocess.run(command + ["eval", "--agent", args.agent,
        "--dataset", str(root / "datasets/refunds.yaml"), "--out", str(destination / "candidate.json")], cwd=root)
    if result.returncode not in (0, 1):
        return result.returncode
    return subprocess.run(command + ["compare", "--baseline", str(root / "benchmarks/baseline.json"),
        "--candidate", str(destination / "candidate.json"), "--thresholds", str(root / "config/ci-thresholds.json"),
        "--out", str(destination / "comparison.json")], cwd=root).returncode


if __name__ == "__main__":
    raise SystemExit(main())
