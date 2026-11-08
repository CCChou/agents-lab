from collections.abc import Iterator
from datetime import datetime
from typing import Protocol, runtime_checkable

from agent.domain.article import Article
from agent.domain.event import Event
from agent.domain.message import Message
from agent.domain.request import AgentRequest
from agent.domain.session import SessionInfo
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

    def delete(self, session_id: str) -> None: ...


@runtime_checkable
class SessionRegistry(Protocol):
    def current(self, owner_id: str) -> str | None: ...

    def set_current(self, owner_id: str, session_id: str) -> None: ...

    def add(self, owner_id: str, session_id: str, created_at: datetime) -> None: ...

    def sessions(self, owner_id: str) -> list[SessionInfo]: ...

    def owners(self) -> list[str]: ...

    def remove(self, owner_id: str, session_id: str) -> None: ...


@runtime_checkable
class ArticleReader(Protocol):
    def read(self, entry_id: int) -> Article: ...


@runtime_checkable
class SessionLifecycle(Protocol):
    """How an entry adapter gets and starts sessions, locally or through the HTTP API (D-035)."""

    def current_or_start(self, owner_id: str) -> str: ...

    def start_new(self, owner_id: str) -> str: ...
