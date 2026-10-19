from collections.abc import Awaitable, Callable
from importlib import import_module
from typing import Any, Protocol

from .models import AgentResponse


class AgentAdapter(Protocol):
    async def run(self, input: dict[str, Any], context: Any) -> AgentResponse: ...


class CallableAdapter:
    def __init__(self, function: Callable[..., Awaitable[AgentResponse]]):
        self.function = function

    async def run(self, input, context) -> AgentResponse:
        response = await self.function(input, context)
        if not isinstance(response, AgentResponse):
            raise TypeError("agent must return AgentResponse")
        return response


def import_object(path: str):
    module, separator, name = path.partition(":")
    if not separator or not module or not name:
        raise ValueError("expected module:attribute")
    return getattr(import_module(module), name)
