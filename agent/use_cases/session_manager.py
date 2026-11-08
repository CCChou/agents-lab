from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import uuid4

from agent.domain.interfaces import ConversationStore, SessionRegistry
from agent.domain.session import RetentionRule


class SessionManager:
    """Owns the session lifecycle: which session each owner is in, and when old ones go."""

    def __init__(
        self,
        registry: SessionRegistry,
        conversations: ConversationStore,
        *,
        new_id: Callable[[], str] = lambda: uuid4().hex,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        rules: Sequence[RetentionRule] = (),
    ) -> None:
        self._registry = registry
        self._conversations = conversations
        self._new_id = new_id
        self._clock = clock
        self._rules = tuple(rules)

    def current_or_start(self, owner_id: str) -> str:
        return self._registry.current(owner_id) or self.start_new(owner_id)

    def start_new(self, owner_id: str) -> str:
        session_id = self._new_id()
        self._registry.add(owner_id, session_id, self._clock())
        self._registry.set_current(owner_id, session_id)
        self.prune()
        return session_id

    def prune(self) -> list[str]:
        """Remove sessions past their owner's retention rule; current sessions always stay."""
        now = self._clock()
        removed: list[str] = []
        for owner_id in self._registry.owners():
            rule = self._rule_for(owner_id)
            if rule is None:
                continue
            current = self._registry.current(owner_id)
            newest_first = reversed(self._registry.sessions(owner_id))
            for position, info in enumerate(newest_first):
                if info.session_id == current:
                    continue
                too_old = rule.max_age is not None and now - info.created_at > rule.max_age
                too_many = rule.keep_last is not None and position >= rule.keep_last
                if too_old or too_many:
                    self._conversations.delete(info.session_id)
                    self._registry.remove(owner_id, info.session_id)
                    removed.append(info.session_id)
        return removed

    def _rule_for(self, owner_id: str) -> RetentionRule | None:
        return next((r for r in self._rules if owner_id.startswith(r.owner_prefix)), None)
