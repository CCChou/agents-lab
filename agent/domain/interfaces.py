from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from agent.domain.message import Message
from agent.domain.tool import Tool, ToolCall


@runtime_checkable
class LLMClient(Protocol):
    def stream(
        self, messages: list[Message], tools: list[Tool] | None = None
    ) -> Iterator[str | ToolCall]: ...
