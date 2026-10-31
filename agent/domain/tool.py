from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    parameters_schema: dict[str, Any]

    def run(self, arguments: dict[str, Any]) -> str: ...
