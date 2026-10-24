# Verification history

## Day 2 — October 24, 2026

Implemented timed and parented tool spans, schema 1.1 experiment metadata, optional usage/cost aggregation, strict paired comparisons, configurable gates, trace inspection, a flawed reference configuration, and GitHub Actions. The dataset still contains the original 20 deterministic fixtures.

Milestone test results: Day 1 baseline **63 passed**; spans **65 passed**; comparison/metadata **79 passed**; CLI **86 passed**; subprocess CI checks **88 passed**; complete-report coverage **89 passed**.

Final full-suite command from the repository root:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp ..\..\work\pytest-day2-full
```

Result: **89 passed in 12.69s**. The explicit temporary directory and disabled pytest cache avoid Windows sandbox directory ownership issues.

The following exact gate commands were also executed through the installed Python environment, with output captured under `runs/day2/`:

```powershell
& .\.venv\Scripts\python.exe scripts/ci_gate.py --agent examples.support_agent:scripted_agent --out runs/day2/baseline
& .\.venv\Scripts\python.exe scripts/ci_gate.py --agent examples.support_agent:flawed_agent --out runs/day2/candidate
& .\.venv\Scripts\python.exe -m agentbench.cli trace --run runs/day2/candidate/candidate.json --scenario refund_above_limit
```

Results: baseline **20/20**, gate exit **0**; flawed configuration **13/20**, gate exit **1**; trace exit **0**, with the blocked authorization attempt and forbidden-call diagnostic verified. Tests confirm the flawed agent's output and final state match the baseline despite those seven unsafe attempts. Invalid/incompatible comparison inputs return exit **2**.

Workflow YAML parsed successfully. The published action interfaces were checked against their upstream documentation. A real hosted Actions run has **not** been verified: this session's GitHub CLI returns 401 and the Git credential helper fails under the sandbox.

The fresh Day 2 installation check was attempted in separate environments with both uv and pip. Both hit Windows sandbox access-denied errors while creating build/temporary files (pip failed during ensurepip), before package installation could finish. Do not treat that check as passed. Day 1's clean installation is recorded below; dependencies and the lockfile are unchanged. The existing installed environment passes the full Day 2 suite and real CLI gate commands.

Initial async tests stalled in Windows asyncio loopback-socket setup; granting network permission resolved that environment issue. The benchmark never called an external model or payment service.

## Day 1

Verified on Windows with Python 3.12.14. Every milestone was tested before the next one began:

| Milestone | Command (project-local Python) | Result |
|---|---|---|
| Package contracts and CLI scaffold | `.venv\Scripts\python.exe -m pytest -q` | 3 passed |
| Mock tools, reference agent, 20 fixtures | same | 32 passed |
| Loader and isolated async runner | same | 41 passed |
| Deterministic evaluators | same | 56 passed |
| Reporting and CLI integration | same | 61 passed |
| Additional timeout/cancellation coverage | same | 63 passed |

## Fresh-environment check

From the project directory, these PowerShell commands selected a new environment outside the source tree:

```powershell
$env:UV_CACHE_DIR=(Join-Path (Resolve-Path '..\..\work') 'uv-cache')
$env:UV_PROJECT_ENVIRONMENT=(Join-Path (Resolve-Path '..\..\work') 'clean-agentbench-venv')
& .\.venv\Scripts\uv.exe sync --extra dev --python .venv\Scripts\python.exe
```

Result: a new environment was created and all 20 resolved packages installed. `uv.lock` records the resolved dependencies. The original development environment was subsequently synchronized with `uv sync --extra dev --locked`.

```powershell
& ..\..\work\clean-agentbench-venv\Scripts\python.exe -m pytest -q
& ..\..\work\clean-agentbench-venv\Scripts\agentbench.exe eval --agent examples.support_agent:scripted_agent --dataset datasets/refunds.yaml --out runs/baseline.json
```

Results: **63 passed**; benchmark **20/20 passed**, exit **0**.

The negative demonstration was also executed from outside the project root, exercising installed package imports rather than relying on the current directory. From `work/`:

```powershell
& .\clean-agentbench-venv\Scripts\agentbench.exe eval --agent examples.support_agent:scripted_agent --dataset ..\outputs\agentbench\datasets\refunds.yaml --max-steps 1 --out ..\outputs\agentbench\runs\limited.json
```

Result: **8/20 passed, 12 failed**, exit **1**. Both reports contain all 20 results, failure diagnostics where appropriate, and matching dataset hashes.

The first editable install predated creation of the examples package and could not import it from the installed CLI. The fresh install and resynchronization fixed this; the outside-directory check verifies the fix. Initial pip setup also encountered restricted network access and a package cache stall; approved network access and workspace-local uv caching completed setup.

At the end of Day 1, spans, comparisons, and CI gates were outstanding; see the Day 2 verification above for their implementation. No performance or LLM-quality claims are inferred from deterministic mock runs.
