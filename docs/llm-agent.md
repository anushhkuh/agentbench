# Optional OpenAI support agent

The adapter lives in `examples/support_agent/llm_agent.py`. It is optional: the deterministic benchmark remains usable without the SDK, credentials, or network access.

## Configure

Run `uv sync --locked --extra dev --extra llm`. Copy `.env.example` to `.env` in the repository root and supply `OPENAI_API_KEY` and `OPENAI_MODEL`. Existing environment variables take precedence over `.env`. The checked-in example has blank values. Do not put credentials in `--settings`.

The current configured experiment uses `gpt-6-luna`. Access depends on the API account. A ChatGPT subscription alone is not evidence of API quota or model access. If a request fails, inspect the sanitized provider exception class, HTTP status, and error code; raw provider response bodies and credentials are not saved.

```sh
uv run agentbench eval --agent examples.support_agent.llm_agent:llm_agent --dataset datasets/refunds.yaml --timeout 120 --concurrency 1 --out runs/llm.json
uv run python scripts/benchmark.py --live --model gpt-6-luna --trials 2 --out runs/live-comparison
```

The second command runs 20 scenarios twice for each of two prompts: 80 case executions, at most 480 model requests with default limits. It exits 0 when comparison thresholds pass, 1 when the comparison gate rejects the candidate, and 2 for setup errors. Limit the dataset with repeated `--scenario` options for a smoke test. The offline mode intentionally demonstrates a rejected flawed agent and returns 0 only when that rejection is observed.

## Request flow

```text
scenario input -> user JSON -> Responses API
                                |
                    function call + reasoning items
                                |
                     validate requested tool name
                                |
                  context.call -> mock tool -> trace
                                |
                    function_call_output with call_id
                                |
                       next Responses request
                                |
                     final structured status JSON
                                |
                    existing deterministic evaluators
```

Each run owns a fresh async SDK client and transcript. Continuations preserve output items, including encrypted reasoning, while requesting `store=False`. No chain-of-thought or raw API transcript is persisted in benchmark artifacts. Observable mock tool calls are traced. The model reads existing refund status through `get_order`; it does not inspect Python state directly.

Two prompt variants are provided: `policy-v1` and `checklist-v1`. Their actual text is hashed into experiment metadata. The CLI invokes the adapter's preflight hook, validates settings, loads credentials, and forces stochastic labelling. Programmatic callers should call `llm_agent.prepare(settings)` and pass the returned settings into `run_dataset`.

Settings: `model`, `prompt`, `max_model_calls` (default 6), `max_output_tokens` (1024), `max_input_bytes` (20000), and `request_timeout` (30 seconds). The runner additionally enforces a case timeout and tool-call limit. `max_input_bytes` bounds the serialized request including tool schemas and transcript; exceeding it fails before another API request. This is a size bound, not an exact tokenizer or provider billing cap.

## Usage and budget

Reported input/output/total tokens are accumulated across responses. When any request lacks usage or fails in flight, `usage_complete` becomes false. Known partial counts remain in the run, but aggregate usage is unknown. No SDK retries occur. Costs are not guessed or silently treated as zero.

The authorized live run had a budget below $5. Planning used the published GPT-6 Luna standard rates, a conservative input allowance including protocol overhead, and the fixed request/output bounds; the 80-case plan plus a smoke test stays below that planning limit. This does not set an account-level billing limit. Check current pricing and account settings before increasing trials, request caps, context size, or using another model.

Earlier attempts failed with `credit_balance_exhausted`. The live GPT-6 Luna comparison completed on October 26, 2026 after credits were added: both policy-v1 and checklist-v1 passed 40/40 (20 scenarios, two trials); the regression gate passed. These stochastic observations do not establish a statistically significant difference. See [live results](../benchmarks/day3-live-summary.json).

## Validation

Offline tests exercise the full loop, SDK request/response serialization through an in-memory HTTP transport, reasoning-item continuation, blocked calls, malformed outputs, missing credentials, metadata, cancellation, limits, partial usage, and redaction. They do not establish real model behavior or account access. CI installs the optional SDK but never supplies a real API key.

Official references: [function calling](https://developers.openai.com/api/docs/guides/function-calling), [Python SDK](https://developers.openai.com/api/reference/python), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), and [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna).
