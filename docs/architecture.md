# Architecture

```text
YAML / JSON -> validated Dataset -> async runner <- callable / run adapter
                                     |
                        semaphore + timeout + copied state
                                     |
                         context.call -> injected mock tools
                                     |
                       attempted calls + output + final state
                                     |
                        output / tool / state evaluators
                                     |
                         redaction -> JSON + Markdown + CLI
```

`models.py` defines serializable contracts. `datasets.py` validates fixtures and hashes canonical content. `adapters.py` wraps callables and resolves trusted imports. `context.py` records attempts before invoking tools, including blocked and cancelled calls. `runner.py` owns orchestration and execution failures; evaluators remain independent from the reference implementation. `storage.py` owns report redaction and writing; `reporting.py` owns aggregation.

The support environment is a copied dictionary, with the tool factory acting as its mutation boundary. Separate environment classes, databases, and registries would add little to this MVP. The scripted agent has trusted access to state to check existing refunds. A future remote adapter should expose that information through an order tool rather than relying on in-process state.

An unsafe attempt can leave correct state because the mock tool refuses it. State checks alone cannot detect this: attempted-call assertions are mandatory for policy-sensitive scenarios. The tests include exactly this case.

Failures are explicit. A runner error or deadline adds a failed execution score. A broken evaluator adds a failed evaluator score while preserving other results. Expected service errors handled by the reference agent can pass, because their scenario explicitly requires safe handling. Partial mutations remain visible after errors and timeouts; no rollback hides them.

`ToolCall` includes timestamps, monotonic duration, IDs, parentage, and outcome status. A context-local ContextVar carries parent spans across nested awaits without mixing simultaneous calls. The runner assigns a root ID before execution so spans reference their run, including failures and cancellations.

`experiments.py` loads schema 1.1 reports, checks complete unique scenario/trial coverage, recomputes outcomes, aggregates known usage/cost, and captures Git provenance. `comparison.py` checks compatible experiment inputs and applies thresholds. `compare` and `trace` consume saved, redacted artifacts. The CI gate script calls the same CLI commands tested locally, while GitHub Actions installs locked dependencies and retains reports.

The versioned baseline is a fixture, not rebuilt on every CI run. Tests prove that the flawed configuration fails despite matching the correct agent's output and state. Strict thresholds prevent an improvement elsewhere from hiding an individual case regression. Host-dependent latency limits are opt-in.
