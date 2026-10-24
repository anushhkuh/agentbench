import asyncio
import json
from pathlib import Path
from enum import Enum

import typer
from rich.console import Console
from rich.table import Table

from .adapters import import_object
from .datasets import load_dataset
from .evaluators import default_evaluators
from .reporting import make_report
from .runner import RunnerConfig, run_dataset
from .storage import save_report, redact
from .experiments import load_report
from .comparison import Thresholds, compare_reports


class ExecutionMode(str, Enum):
    deterministic = "deterministic"
    stochastic = "stochastic"

app = typer.Typer(no_args_is_help=True, help="Evaluate tool-using agents against isolated scenarios.")


@app.command()
def version():
    """Show the installed MVP version."""
    typer.echo("AgentBench 0.1.0")


@app.command("eval")
def evaluate(
    agent: str = typer.Option(..., help="Trusted async callable or adapter instance as module:attribute"),
    dataset: Path = typer.Option(..., exists=True, dir_okay=False),
    out: Path = typer.Option(Path("runs"), help="Output directory or JSON filename"),
    tools: str = typer.Option("examples.support_agent.tools:support_tools", help="Tool factory as module:attribute"),
    concurrency: int = typer.Option(4, min=1),
    timeout: float = typer.Option(5, min=0.001),
    max_steps: int = typer.Option(20, min=1),
    trials: int = typer.Option(1, min=1),
    settings: str = typer.Option("{}", help="JSON object passed to context.settings"),
    mode: ExecutionMode = typer.Option(ExecutionMode.deterministic, help="Declared execution mode; not inferred from the adapter"),
    model_id: str | None = typer.Option(None),
    prompt_id: str | None = typer.Option(None),
):
    """Run deterministic assertions; exit 1 on failed cases and 2 on invalid setup."""
    console = Console(highlight=False, markup=False)
    try:
        data = load_dataset(dataset)
        config = RunnerConfig(concurrency=concurrency, timeout_seconds=timeout, max_steps=max_steps, trials=trials)
        agent_settings = json.loads(settings)
        if not isinstance(agent_settings, dict):
            raise ValueError("settings must be a JSON object")
        adapter, factory = import_object(agent), import_object(tools)
        results = asyncio.run(run_dataset(data, adapter, factory, config=config,
                                         evaluators=default_evaluators(), settings=agent_settings))
        report = make_report(data, results, agent, tools, config, agent_settings,
                             execution_mode=mode.value, model_id=model_id, prompt_id=prompt_id)
        path, safe = save_report(report, out)
    except (ValueError, OSError, ImportError, AttributeError, TypeError) as error:
        console.print(f"Invalid setup: {error}")
        raise typer.Exit(2) from error
    table = Table("Scenario", "Trial", "Result", "Reason")
    for run in safe["runs"]:
        table.add_row(run["scenario_id"], str(run["trial"]), "PASS" if run["passed"] else "FAIL",
                      "; ".join(score["reason"] for score in run["scores"] if not score["passed"]))
    console.print(table)
    summary = safe["summary"]
    console.print(f"Passed {summary['passed']}/{summary['total']} ({summary['pass_rate']:.0%}); "
                  f"p50 {summary['latency_p50_ms']:.2f} ms; p95 {summary['latency_p95_ms']:.2f} ms")
    console.print(f"Mode: {mode.value}; usage: {summary['usage'] if summary['usage'] is not None else 'unknown'}; "
                  f"cost (USD): {summary['cost'] if summary['cost'] is not None else 'unknown'}")
    console.print(f"JSON: {path}")
    raise typer.Exit(0 if summary["failed"] == 0 else 1)


@app.command("compare")
def compare(
    baseline: Path = typer.Option(..., exists=True, dir_okay=False),
    candidate: Path = typer.Option(..., exists=True, dir_okay=False),
    thresholds: Path | None = typer.Option(None, exists=True, dir_okay=False, help="JSON threshold configuration"),
    min_pass_rate: float | None = typer.Option(None, min=0, max=1),
    max_pass_rate_drop: float | None = typer.Option(None, min=0, max=1),
    max_case_regressions: int | None = typer.Option(None, min=0),
    max_p95_increase_pct: float | None = typer.Option(None, min=0),
    out: Path | None = typer.Option(None, help="Optional comparison JSON file"),
):
    """Gate paired experiments. Exit 1 for a regression, 2 for incompatible/invalid reports."""
    console = Console(markup=False, highlight=False)
    try:
        values = json.loads(thresholds.read_text(encoding="utf-8")) if thresholds else {}
        if not isinstance(values, dict):
            raise ValueError("thresholds must be a JSON object")
        for key, value in {"min_pass_rate": min_pass_rate, "max_pass_rate_drop": max_pass_rate_drop,
                           "max_case_regressions": max_case_regressions, "max_p95_increase_pct": max_p95_increase_pct}.items():
            if value is not None:
                values[key] = value
        result = compare_reports(load_report(baseline), load_report(candidate), Thresholds.model_validate(values))
        if out:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(redact(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (ValueError, OSError) as error:
        console.print(f"Cannot compare: {error}")
        raise typer.Exit(2) from error
    console.print(f"Mode: {result['execution_mode']}")
    if result["execution_mode"] == "stochastic":
        console.print("Observed sample comparison only; this gate does not establish statistical significance.")
    table = Table("Metric", "Baseline", "Candidate")
    for key in ("pass_rate", "latency_p50_ms", "latency_p95_ms", "usage", "cost"):
        table.add_row(key, *(str(result[side][key]) if result[side][key] is not None else "unknown" for side in ("baseline", "candidate")))
    console.print(table)
    for item in result["regressions"]:
        console.print(f"REGRESSION {item['scenario_id']} trial {item['trial']}")
    for reason in result["violations"]:
        console.print(reason)
    console.print("Gate: PASS" if result["passed"] else "Gate: FAIL")
    raise typer.Exit(0 if result["passed"] else 1)


@app.command("trace")
def trace(
    run: Path = typer.Option(..., exists=True, dir_okay=False),
    scenario: str = typer.Option(...),
    trial: int = typer.Option(1, min=1),
):
    """Inspect tool sequence, inputs/results, errors, and evaluator diagnostics."""
    console = Console(markup=False, highlight=False)
    try:
        report = redact(load_report(run))
        result = next((r for r in report["runs"] if r["scenario_id"] == scenario and r["trial"] == trial), None)
        if result is None:
            raise ValueError(f"scenario/trial not found: {scenario}/{trial}")
    except (ValueError, OSError) as error:
        console.print(f"Cannot read trace: {error}")
        raise typer.Exit(2) from error
    console.print(f"{scenario} trial {trial}: {'PASS' if result['passed'] else 'FAIL'} ({result['status']})")
    for call in result["calls"]:
        duration = f"{call['duration_ms']:.3f} ms" if call["duration_ms"] is not None else "unknown duration"
        console.print(f"{call['started_at']} {call['name']} {call['status']} {duration}")
        console.print(f"  span={call['id']} parent={call['parent_id']} run={call['run_id']}")
        console.print(f"  inputs: {json.dumps(call['arguments'])}")
        console.print(f"  result: {json.dumps(call['result'])}")
        if call["error"]:
            console.print(f"  error: {call['error']}")
    if result["error"]:
        console.print(f"Execution error: {result['error']}")
    for score in result["scores"]:
        if not score["passed"]:
            console.print(f"FAIL {score['evaluator']}: {score['reason']}")
    console.print(f"Output: {json.dumps(result['output'])}")
    console.print(f"Final state: {json.dumps(result['final_state'])}")


if __name__ == "__main__":
    app()
