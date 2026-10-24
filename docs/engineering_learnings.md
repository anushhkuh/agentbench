# Engineering tradeoffs

1. **State and attempts answer different questions.** State shows what changed; attempts show whether an agent tried to violate policy. The flawed agent demonstrates why both matter even when the final answer is correct.
2. **Isolation prevents fixture order from changing results.** State, input, and settings are copied per case/trial. External adapter globals are not isolated.
3. **Record before dispatch.** Authorization failures, unknown tools, exceptions, and cancellation must remain visible. Context variables preserve nested parentage under concurrency.
4. **Timeouts retain partial effects.** Cancellation closes spans and partial state remains available for evaluation. There are no hidden retries or rollbacks. Deadlines are cooperative; hostile code needs process isolation.
5. **Test evaluators with counterexamples.** Tests cover false-looking successes, duplicate actions, missing fields, incompatible data, threshold boundaries, and incorrect cached summaries. Execution failures cannot pass solely because output/state checks pass.
6. **Fair comparisons need matching inputs.** Dataset hash/version, case/trial coverage, evaluator versions, runner settings, tools, and mode must agree. Agent/model/prompt settings can differ intentionally. Artifacts are trusted inputs, not tamper-proof evidence.
7. **LLM judges remain deferred.** A future judge needs versioned rubrics, human-labelled calibration, disagreement analysis, and uncertainty reporting. It must not replace deterministic authorization checks.
8. **Scaling needs bounded scheduling too.** The semaphore bounds active agents, but one coroutine is created per case/trial. Large workloads need a queue, process isolation, durable results, rate limiting, retry policy, and distributed ownership.
9. **Tracing adds copying, timestamps, and serialization.** No isolated overhead benchmark has been run. Measure identical adapters with/without instrumentation over repeated warm runs before making performance claims. Mock-tool latency is not LLM speed.
10. **Keep the core inspectable.** Explicit adapters, synchronous evaluators, JSON reports, and one CLI avoid services/UI dependencies. SQLite, providers, and a dashboard can be added independently.

Workflow references: [checkout](https://github.com/actions/checkout), [setup-uv](https://github.com/astral-sh/setup-uv), and [upload-artifact](https://github.com/actions/upload-artifact). Dependency resolution is locked in `uv.lock`. Local subprocess tests verify the gate; a hosted Actions run is a separate check.
