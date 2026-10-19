# Day 1 demo

From the repository root after setup:

1. Run `agentbench eval --agent examples.support_agent:scripted_agent --dataset datasets/refunds.yaml --out runs/baseline.json`.
2. Observe all 20 cases passing. Open the report and find `refund_above_limit`: approval is requested, with no refund recorded.
3. Run `agentbench eval --agent examples.support_agent:scripted_agent --dataset datasets/refunds.yaml --max-steps 1 --out runs/limited.json`.
4. Observe exit code 1 and the failed cases. Open `runs/limited.json`, locate `refund_valid`, and inspect execution, output, and state diagnostics. The first lookup completed, but the refund could not execute within the configured call limit.
5. Run `python -m pytest -q`. The evaluator tests also demonstrate that an unauthorized attempt fails even when mock authorization prevents the mutation.

This demo uses a constrained run to illustrate diagnosis. A second flawed agent, comparison command, and CI gate are Day 2 work.
