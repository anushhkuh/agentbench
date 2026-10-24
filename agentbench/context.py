from copy import deepcopy
from contextvars import ContextVar
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4
import asyncio
from .models import ToolCall


class StepLimitExceeded(Exception):
    pass


class AgentContext:
    def __init__(self, state, tool_factory, max_steps=20, settings=None, run_id=None):
        self.state = state
        self.tools = tool_factory(state)
        self.max_steps = max_steps
        self.settings = deepcopy(settings or {})
        self.calls = []
        self.limit_exceeded = False
        self.run_id = run_id or str(uuid4())
        self._parent = ContextVar(f"parent_{self.run_id}", default=None)

    async def call(self, name, **arguments):
        if len(self.calls) >= self.max_steps:
            self.limit_exceeded = True
            raise StepLimitExceeded("maximum tool calls exceeded")
        started = perf_counter()
        call = ToolCall(name=name, arguments=deepcopy(arguments), run_id=self.run_id,
                        parent_id=self._parent.get() or self.run_id,
                        started_at=datetime.now(timezone.utc))
        self.calls.append(call)  # Record attempts before authorization or execution.
        parent_token = self._parent.set(call.id)
        try:
            result = await self.tools[name](**arguments)
            call.result = deepcopy(result)
            call.status = "success"
            return result
        except BaseException as error:
            call.error = f"{type(error).__name__}: {error}"
            call.status = "cancelled" if isinstance(error, asyncio.CancelledError) else "error"
            raise
        finally:
            call.duration_ms = (perf_counter() - started) * 1000
            call.ended_at = datetime.now(timezone.utc)
            self._parent.reset(parent_token)
