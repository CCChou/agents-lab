from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from agent.domain.message import Message


@runtime_checkable
class LLMClient(Protocol):
    def stream(self, messages: list[Message]) -> Iterator[str]: ...
