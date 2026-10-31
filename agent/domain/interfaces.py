from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from agent.domain.event import Event
from agent.domain.message import Message
from agent.domain.request import AgentRequest
from agent.domain.tool import Tool, ToolCall


@runtime_checkable
class Agent(Protocol):
    name: str

    def run(self, request: AgentRequest) -> Iterator[Event]: ...


@runtime_checkable
class LLMClient(Protocol):
    def stream(
        self, messages: list[Message], tools: list[Tool] | None = None
    ) -> Iterator[str | ToolCall]: ...


@runtime_checkable
class ConversationStore(Protocol):
    def load(self, session_id: str) -> list[Message]: ...

    def append(self, session_id: str, messages: list[Message]) -> None: ...
