# Day 2 demo

From the repository root after `uv sync --locked --extra dev`:

1. Run `uv run agentbench eval --agent examples.support_agent:scripted_agent --dataset datasets/refunds.yaml --out runs/baseline.json`. All 20 fixtures pass.
2. Run `uv run agentbench eval --agent examples.support_agent:flawed_agent --dataset datasets/refunds.yaml --out runs/candidate.json`. Expect 13/20 and exit 1.
3. Run `uv run agentbench trace --run runs/candidate.json --scenario refund_above_limit`. Find the failed refund span, authorization error, and successful approval. The forbidden attempt fails evaluation despite correct final state.
4. Run `uv run agentbench compare --baseline runs/baseline.json --candidate runs/candidate.json`. Expect seven case regressions and exit 1.
5. Run `uv run python scripts/ci_gate.py` for exit 0. Repeat with `--agent examples.support_agent:flawed_agent` for exit 1.
6. Once pushed, manually run **AgentBench regression gate** in GitHub Actions, selecting the flawed adapter to demonstrate a red run. Download `benchmark-reports` for diagnostics. A hosted run is separate from local verification.

No API keys, real refunds, or stochastic model calls are involved. The alternative configuration is `--settings '{"unsafe_refund_first": true}'` with the scripted adapter; the exported flawed adapter avoids platform-specific JSON shell quoting.
