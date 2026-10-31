from collections import defaultdict

from agent.domain.message import Message


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._sessions: defaultdict[str, list[Message]] = defaultdict(list)

    def load(self, session_id: str) -> list[Message]:
        return list(self._sessions[session_id])

    def append(self, session_id: str, messages: list[Message]) -> None:
        self._sessions[session_id].extend(messages)
