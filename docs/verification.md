# Day 1 verification

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

Day 2 has not begun. Full spans, comparisons, and CI regression gates remain outstanding. No performance or LLM-quality claims are inferred from this deterministic local run.
