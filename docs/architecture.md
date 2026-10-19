# Day 1 architecture

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

Day 2 can enrich ToolCall into timed spans without changing the tool dispatch boundary, add experiment compatibility checks around the dataset hash, and add CI threshold commands around report summaries. No such features are claimed complete here.
