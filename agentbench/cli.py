import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .adapters import import_object
from .datasets import load_dataset
from .evaluators import default_evaluators
from .reporting import make_report
from .runner import RunnerConfig, run_dataset
from .storage import save_report

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
        report = make_report(data, results, agent, tools, config, agent_settings)
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
    console.print("Usage/cost: unknown")
    console.print(f"JSON: {path}")
    raise typer.Exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    app()
