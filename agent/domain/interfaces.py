from collections.abc import Iterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    def stream(self, prompt: str) -> Iterator[str]: ...
