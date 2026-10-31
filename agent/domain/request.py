from dataclasses import dataclass

from agent.domain.message import Message


@dataclass(frozen=True)
class AgentRequest:
    session_id: str
    message: Message
