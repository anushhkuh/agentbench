import asyncio
from copy import deepcopy
from time import perf_counter
from uuid import uuid4

from pydantic import Field

from .adapters import CallableAdapter
from .context import AgentContext, StepLimitExceeded
from .models import AgentResponse, Contract, EvaluationRun, Score


class RunnerConfig(Contract):
    concurrency: int = Field(default=4, ge=1)
    timeout_seconds: float = Field(default=5, gt=0, allow_inf_nan=False)
    max_steps: int = Field(default=20, ge=1)
    trials: int = Field(default=1, ge=1)


async def run_dataset(dataset, agent, tool_factory, *, config=None, evaluators=(), settings=None):
    config = config or RunnerConfig()
    adapter = agent if hasattr(agent, "run") else CallableAdapter(agent)
    semaphore = asyncio.Semaphore(config.concurrency)

    async def execute(scenario, trial):
        async with semaphore:
            started = perf_counter()
            state = deepcopy(scenario.initial_state)
            context = None
            response = None
            run_id = str(uuid4())
            status, error = "completed", None
            deadline = asyncio.timeout(config.timeout_seconds)
            try:
                context = AgentContext(state, tool_factory, config.max_steps, settings, run_id=run_id)
                async with deadline:
                    response = await adapter.run(deepcopy(scenario.input), context)
                if deadline.expired():
                    raise TimeoutError("agent suppressed timeout cancellation")
                if not isinstance(response, AgentResponse):
                    raise TypeError("agent must return AgentResponse")
                if context.limit_exceeded:
                    raise StepLimitExceeded("maximum tool calls exceeded")
            except TimeoutError as exc:
                if deadline.expired():
                    status, error = "timeout", f"exceeded {config.timeout_seconds:g}s timeout"
                else:
                    status, error = "error", f"TimeoutError: {exc}"
            except StepLimitExceeded as exc:
                status, error = "step_limit", str(exc)
            except Exception as exc:
                status, error = "error", f"{type(exc).__name__}: {exc}"
            run = EvaluationRun(
                id=run_id, scenario_id=scenario.id, trial=trial, status=status,
                output=response.output if response else None,
                usage=response.usage if response else None,
                cost_usd=response.cost_usd if response else None,
                final_state=deepcopy(state), calls=context.calls if context else [],
                latency_ms=(perf_counter() - started) * 1000, error=error,
            )
            run.scores.append(Score(evaluator="execution", passed=status == "completed",
                                    reason=error or "agent completed"))
            for evaluator in evaluators:
                try:
                    run.scores.append(evaluator.evaluate(run, scenario, run.final_state))
                except Exception as exc:
                    run.scores.append(Score(evaluator=type(evaluator).__name__, passed=False,
                                            reason=f"evaluator error: {type(exc).__name__}: {exc}"))
            return run

    return await asyncio.gather(*(execute(scenario, trial)
                                  for scenario in dataset.scenarios
                                  for trial in range(1, config.trials + 1)))
