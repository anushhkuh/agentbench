# AgentBench — Day 1 MVP

A local Python evaluation harness for tool-using agents. It checks observable tool attempts and final environment state alongside the agent's output. All refund operations are simulated; no API key or external account is needed.

## Setup

Python 3.12+ is required. From this directory, with `uv` installed:

```sh
uv sync --extra dev
uv run agentbench eval --agent examples.support_agent:scripted_agent --dataset datasets/refunds.yaml --out runs/baseline.json
uv run pytest -q
```

Alternatively, use a Python virtual environment:

```sh
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
agentbench eval --agent examples.support_agent:scripted_agent --dataset datasets/refunds.yaml --out runs/baseline.json
```

The baseline should report `Passed 20/20 (100%)`. Latencies are measured per execution and will vary. JSON and Markdown reports are written together. `--out runs/` chooses a unique experiment filename; an explicit JSON filename is overwritten on rerun.

## Demonstrate a failure

```sh
agentbench eval --agent examples.support_agent:scripted_agent --dataset datasets/refunds.yaml --max-steps 1 --out runs/limited.json
```

This deliberately starves the agent of tool calls. The command exits **1** and reports failures with reasons. Inspect `runs/limited.json`: each result contains status, output, attempted calls (including errors), final state, evaluator scores, and evidence. Exit **0** means all cases passed; **2** means invalid setup or report-writing failure.

## SDK and extension points

An agent is an async function returning `AgentResponse`, or an instance with `async run(input, context)`. Use `context.call(name, **arguments)` for observable tool attempts. `context.settings` receives `--settings '{"key":"value"}'`. A tool factory accepts the copied scenario state and returns a dictionary of async tool functions. Select it with `--tools module:factory`.

```python
from agentbench.models import AgentResponse

async def agent(input, context):
    order = await context.call("get_order", order_id=input["order_id"])
    return AgentResponse(output={"found": order is not None})
```

The Python runner accepts an explicit evaluator list; the CLI installs the three deterministic evaluators by default. An evaluator implements `evaluate(run, scenario, final_state) -> Score`. Execution errors independently fail a run. Tools and evaluators are injected; the runner has no refund-specific branches.

## Scenarios and assertions

`datasets/refunds.yaml` contains 20 fixtures: valid refunds, boundary amounts, configurable limits, denial, unknown orders, duplicate refunds and approvals, service failures, missing input, and malicious tool-response text. Amounts are **integer cents**, avoiding floating-point financial calculations. Only full-order refunds are supported. Tool mutations enforce eligibility, amount, policy limit, and idempotency.

Each YAML/JSON dataset has a version and unique scenario IDs. `expected` supports:

- `output`: exact JSON value (including explicit `null`); omitted means no exact check. `check_output: false` explicitly disables it.
- `output_fields`: required top-level output keys and exact values; extra keys are allowed.
- `required_tools`, `forbidden_tools`, `max_calls`: assertions over attempted calls, including blocked calls.
- `state`: assertions with a path list, an operation (`equals`, `length`, or `unique`), and a value. Empty path selects the whole state. For `unique`, the value names the item key, or `null` compares whole items.

The reference fixtures assert the entire final state, so unrelated mutations also fail. Required tool calls mean attempts, not guaranteed success; combine them with state/output assertions. Expected, safely handled mock tool errors pass their scenario; unhandled exceptions fail execution.

## Runner and report behavior

Use `--concurrency 4 --timeout 5 --max-steps 20 --trials 1` to control execution. Each scenario/trial copies initial state, input, and settings. Results remain in dataset/trial order regardless of completion order. A timeout preserves partial state and captured attempts. The maximum-step setting counts tool calls, not internal reasoning steps. Dataset hashes cover validated semantic content, including expectations and order; formatting changes do not affect the hash.

Reports include schema version, experiment UUID/time, agent and tool identifiers, runner/settings, dataset version/hash, evaluator versions, p50/p95 latency, results, and diagnostics. Latency includes context setup and agent execution, excludes semaphore queueing and evaluation. Individual response usage can be recorded; aggregate usage and cost are currently unknown.

## Scope and limits

- Day 1 is implemented. Day 2's timed/parented spans, experiment comparison, `trace` command, flawed configuration, and CI regression gates are not implemented. SQLite and optional integrations are deferred.
- Adapters are **trusted local Python**, imported explicitly. This is not a sandbox. Agents can access state, bypass wrappers, spawn background tasks, or block the event loop. Only `context.call` activity is observed.
- Timeouts require cooperative async code. Cancellation that returns is marked timed out; indefinitely blocking or cancellation-resistant code needs process isolation, outside this MVP.
- Redaction covers common sensitive field names, known sensitive-string echoes, emails, and Bearer credentials at persistence. It is heuristic, not a complete PII detector. Do not use real customer data without a domain-specific redaction policy. Evaluation uses unredacted in-memory values.
- Deterministic output checks are exact/field checks, not arbitrary JSON Schema or LLM judging. The scripted injection fixtures verify this baseline's behavior; they do not establish general LLM resistance.
- No retries, real refunds, API server, UI, provider integration, or distributed scheduler.

See [architecture](docs/architecture.md), [demo](docs/demo.md), and [verification](docs/verification.md).
