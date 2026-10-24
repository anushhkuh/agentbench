# AgentBench — Agent evaluation and regression gates

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

## Diagnose a policy regression

```sh
uv run agentbench eval --agent examples.support_agent:scripted_agent --dataset datasets/refunds.yaml --out runs/baseline.json
uv run agentbench eval --agent examples.support_agent:flawed_agent --dataset datasets/refunds.yaml --out runs/candidate.json
uv run agentbench trace --run runs/candidate.json --scenario refund_above_limit
uv run agentbench compare --baseline runs/baseline.json --candidate runs/candidate.json --out runs/comparison.json
```

The flawed agent attempts an above-policy refund before requesting approval. The mock tool blocks it. Its answers and final state still match the baseline, but **7 forbidden-action scenarios fail**, for **13/20 passing**. `eval` and `compare` return exit 1 for this demonstration. `trace` succeeds with exit 0 when it can display a trace, even if that run failed.

Each instrumented call records a span ID, run/parent IDs, UTC start/end timestamps, monotonic duration, inputs, results, and success/error/cancellation status. Nested and concurrent calls retain separate parent relationships. Run IDs are root parents; nested spans point to their calling span. Step-limit rejections fail execution before dispatch and do not add another tool span.

## Regression gates and comparisons

```sh
uv run python scripts/ci_gate.py
uv run python scripts/ci_gate.py --agent examples.support_agent:flawed_agent
```

The first command passes; the second exits 1. Both use the same gate as `.github/workflows/ci.yml`, comparing against `benchmarks/baseline.json`. The workflow runs on pushes and pull requests, saves reports even on failure, and supports manual `flawed_agent` selection to demonstrate a failing Actions run. Local subprocess tests verify both outcomes; hosted execution requires pushing the change and an available Actions runner.

`config/ci-thresholds.json` requires a 100% pass rate, no pass-rate drop, and no previously passing scenario/trial failures. Optional latency gating is disabled because host timing varies. Supply thresholds with `--thresholds file.json` or override them with `--min-pass-rate`, `--max-pass-rate-drop`, `--max-case-regressions`, and `--max-p95-increase-pct`. Rates use fractions (0.05 means five percentage points); the latency option uses a percentage (20 means 20%). Default comparison thresholds match the strict CI policy.

Comparisons reject mismatched dataset hashes/versions, evaluator versions, runner settings, tool factories, execution modes, and scenario/trial coverage. Invalid or incompatible input exits 2. Loading recomputes outcomes and summary metrics from run scores rather than trusting saved aggregate/pass flags. Comparison JSON includes per-scenario pass rates and paired regressions/improvements.

For provider-backed agents, set `--mode stochastic --model-id ... --prompt-id ...`. Mode is a caller declaration, not an automatic determinism check. Stochastic comparison reports observed differences only, without statistical significance testing. `AgentResponse` accepts optional `usage` metrics and `cost_usd`. A metric is totaled only if every run supplies it; missing values remain unknown. Costs are supplied by the adapter, never estimated by the harness.

When intentionally changing fixtures, review them and regenerate the approved baseline with `uv run agentbench eval --agent examples.support_agent:scripted_agent --dataset datasets/refunds.yaml --out benchmarks/baseline.json`. Do not regenerate it automatically in CI. The checked-in baseline records the parent Git revision plus a dirty-tree flag because it was captured during Day 2 implementation. Its timings are illustrative, not a performance target. Reports are trusted local artifacts, not signed attestations against deliberate tampering.

## Demonstrate a call-limit failure

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

Schema 1.1 reports include experiment UUID/time, agent/tool identifiers, runner/settings, model/prompt identifiers, Git revision and dirty status, execution mode, dataset version/hash and scenario IDs, evaluator versions, p50/p95 latency, optional usage/cost, results, and diagnostics. Code provenance refers to the harness source checkout; external adapters should record versions in settings. Latency includes context setup and agent execution, excludes semaphore queueing and evaluation. `compare` and `trace` require schema 1.1; regenerate Day 1 reports before using them.

## Scope and limits

- Day 1 and Day 2 functionality are implemented and locally tested. SQLite and optional integrations remain deferred.
- Adapters are **trusted local Python**, imported explicitly. This is not a sandbox. Agents can access state, bypass wrappers, spawn background tasks, or block the event loop. Only `context.call` activity is observed.
- Timeouts require cooperative async code. Cancellation that returns is marked timed out; indefinitely blocking or cancellation-resistant code needs process isolation, outside this MVP.
- Redaction covers common sensitive field names, known sensitive-string echoes, emails, and Bearer credentials at persistence. It is heuristic, not a complete PII detector. Do not use real customer data without a domain-specific redaction policy. Evaluation uses unredacted in-memory values.
- Deterministic output checks are exact/field checks, not arbitrary JSON Schema or LLM judging. The scripted injection fixtures verify this baseline's behavior; they do not establish general LLM resistance.
- No retries, real refunds, API server, UI, provider integration, or distributed scheduler.

See [architecture](docs/architecture.md), [demo](docs/demo.md), and [verification](docs/verification.md).
