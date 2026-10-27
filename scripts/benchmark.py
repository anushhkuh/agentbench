"""Repeat two configurations and save reports. Live execution is explicit."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from agentbench.datasets import load_dataset


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call the paid OpenAI API using the local environment/.env")
    parser.add_argument("--model", help="Explicit API model; overrides OPENAI_MODEL")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--scenario", action="append", help="Limit to these scenario IDs (repeat this option)")
    parser.add_argument("--max-model-calls", type=int, default=6)
    parser.add_argument("--max-output-tokens", type=int, default=1024)
    parser.add_argument("--out", type=Path, default=root / "runs/repeated")
    args = parser.parse_args()
    if not 1 <= args.trials <= 20:
        parser.error("trials must be between 1 and 20")
    destination = args.out.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    data = load_dataset(root / "datasets/refunds.yaml")
    if args.scenario:
        ids = set(args.scenario)
        if ids - {s.id for s in data.scenarios}:
            parser.error("unknown scenario ID")
        data.scenarios = [s for s in data.scenarios if s.id in ids]
    dataset = destination / "dataset.json"
    dataset.write_text(data.model_dump_json(indent=2), encoding="utf-8")
    command = [sys.executable, "-m", "agentbench.cli"]
    names = ["policy-v1", "checklist-v1"] if args.live else ["scripted_agent", "flawed_agent"]
    if args.live:
        print(f"LIVE API: up to {2 * len(data.scenarios) * args.trials * args.max_model_calls} model requests. Provider charges apply.", flush=True)
    for index, name in enumerate(names):
        label = "baseline" if index == 0 else "candidate"
        agent = "examples.support_agent.llm_agent:llm_agent" if args.live else f"examples.support_agent:{name}"
        settings = ({"prompt": name, "max_model_calls": args.max_model_calls,
                     "max_output_tokens": args.max_output_tokens} if args.live else {})
        if args.live and args.model:
            settings["model"] = args.model
        invocation = command + ["eval", "--agent", agent, "--dataset", str(dataset),
            "--out", str(destination / f"{label}.json"), "--trials", str(args.trials),
            "--concurrency", "1", "--timeout", "120" if args.live else "5", "--settings", json.dumps(settings)]
        result = subprocess.run(invocation, cwd=root)
        if result.returncode not in (0, 1):
            return result.returncode
    result = subprocess.run(command + ["compare", "--baseline", str(destination / "baseline.json"),
        "--candidate", str(destination / "candidate.json"), "--out", str(destination / "comparison.json")], cwd=root)
    if result.returncode == 2:
        return 2
    print(f"Reports saved to {destination}. Comparison exit code: {result.returncode}")
    if args.live:
        print("These are stochastic observations, not a statistical significance test or deterministic replay.")
        return result.returncode
    # Offline demo succeeds only when the deliberately flawed configuration is rejected.
    return 0 if result.returncode == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
