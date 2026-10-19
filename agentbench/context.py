from copy import deepcopy
from .models import ToolCall


class StepLimitExceeded(Exception):
    pass


class AgentContext:
    def __init__(self, state, tool_factory, max_steps=20, settings=None):
        self.state = state
        self.tools = tool_factory(state)
        self.max_steps = max_steps
        self.settings = deepcopy(settings or {})
        self.calls = []
        self.limit_exceeded = False

    async def call(self, name, **arguments):
        if len(self.calls) >= self.max_steps:
            self.limit_exceeded = True
            raise StepLimitExceeded("maximum tool calls exceeded")
        call = ToolCall(name=name, arguments=deepcopy(arguments))
        self.calls.append(call)  # Record attempts before authorization or execution.
        try:
            result = await self.tools[name](**arguments)
            call.result = deepcopy(result)
            return result
        except BaseException as error:
            call.error = f"{type(error).__name__}: {error}"
            raise
