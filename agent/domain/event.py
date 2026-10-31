from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolStarted:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolLimitReached:
    pass


Event = TextDelta | ToolStarted | ToolLimitReached
