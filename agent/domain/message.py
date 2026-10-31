from dataclasses import dataclass
from typing import Literal

from agent.domain.tool import ToolCall

Role = Literal["user", "assistant", "system", "tool"]


@dataclass(frozen=True)
class TextPart:
    text: str


ContentPart = TextPart


@dataclass(frozen=True)
class Message:
    role: Role
    content: list[ContentPart]
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

    @classmethod
    def from_text(
        cls,
        role: Role,
        text: str,
        *,
        tool_calls: list[ToolCall] | None = None,
        tool_call_id: str | None = None,
    ) -> "Message":
        content: list[ContentPart] = [TextPart(text)] if text else []
        return cls(role, content, tool_calls=tool_calls, tool_call_id=tool_call_id)

    @property
    def text(self) -> str:
        return "".join(part.text for part in self.content)
