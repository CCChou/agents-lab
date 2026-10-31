from dataclasses import dataclass
from typing import Literal

from agent.domain.tool import ToolCall

Role = Literal["user", "assistant", "system", "tool"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
