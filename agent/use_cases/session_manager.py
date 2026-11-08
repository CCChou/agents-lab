from collections.abc import Callable
from uuid import uuid4

from agent.domain.interfaces import SessionRegistry


class SessionManager:
    """Owns the session lifecycle: which session each owner is currently in."""

    def __init__(
        self,
        registry: SessionRegistry,
        new_id: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        self._registry = registry
        self._new_id = new_id

    def current_or_start(self, owner_id: str) -> str:
        return self._registry.current(owner_id) or self.start_new(owner_id)

    def start_new(self, owner_id: str) -> str:
        session_id = self._new_id()
        self._registry.set_current(owner_id, session_id)
        return session_id
