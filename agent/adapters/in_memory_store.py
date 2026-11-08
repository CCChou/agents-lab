from collections import defaultdict

from agent.domain.message import Message


class InMemorySessionStore:
    """Implements both ConversationStore and SessionRegistry over the same data."""

    def __init__(self) -> None:
        self._sessions: defaultdict[str, list[Message]] = defaultdict(list)
        self._current: dict[str, str] = {}

    def load(self, session_id: str) -> list[Message]:
        return list(self._sessions[session_id])

    def append(self, session_id: str, messages: list[Message]) -> None:
        self._sessions[session_id].extend(messages)

    def current(self, owner_id: str) -> str | None:
        return self._current.get(owner_id)

    def set_current(self, owner_id: str, session_id: str) -> None:
        self._current[owner_id] = session_id
