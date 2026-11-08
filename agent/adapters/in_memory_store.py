from collections import defaultdict
from datetime import datetime

from agent.domain.message import Message
from agent.domain.session import SessionInfo


class InMemorySessionStore:
    """Implements both ConversationStore and SessionRegistry over the same data."""

    def __init__(self) -> None:
        self._sessions: defaultdict[str, list[Message]] = defaultdict(list)
        self._current: dict[str, str] = {}
        self._owned: dict[str, dict[str, datetime]] = {}

    def load(self, session_id: str) -> list[Message]:
        return list(self._sessions[session_id])

    def append(self, session_id: str, messages: list[Message]) -> None:
        self._sessions[session_id].extend(messages)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def current(self, owner_id: str) -> str | None:
        return self._current.get(owner_id)

    def set_current(self, owner_id: str, session_id: str) -> None:
        self._current[owner_id] = session_id

    def add(self, owner_id: str, session_id: str, created_at: datetime) -> None:
        self._owned.setdefault(owner_id, {})[session_id] = created_at

    def sessions(self, owner_id: str) -> list[SessionInfo]:
        owned = self._owned.get(owner_id, {})
        infos = [SessionInfo(session_id, created) for session_id, created in owned.items()]
        return sorted(infos, key=lambda info: info.created_at)

    def owners(self) -> list[str]:
        return list(self._owned)

    def remove(self, owner_id: str, session_id: str) -> None:
        owned = self._owned.get(owner_id, {})
        owned.pop(session_id, None)
        if not owned:
            self._owned.pop(owner_id, None)
