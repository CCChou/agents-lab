from datetime import UTC, datetime, timedelta

from agent.adapters.in_memory_store import InMemorySessionStore
from agent.domain.interfaces import SessionLifecycle
from agent.domain.message import Message
from agent.domain.session import RetentionRule, SessionInfo
from agent.use_cases.session_manager import SessionManager

T0 = datetime(2026, 11, 1, tzinfo=UTC)


class FakeClock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


def make_manager(
    *ids: str, rules: tuple[RetentionRule, ...] = ()
) -> tuple[SessionManager, InMemorySessionStore, FakeClock]:
    store = InMemorySessionStore()
    clock = FakeClock()
    manager = SessionManager(store, store, new_id=iter(ids).__next__, clock=clock, rules=rules)
    return manager, store, clock


# --- lifecycle ---


def test_current_or_start_starts_a_session_on_first_use():
    sessions, store, _ = make_manager("s1")

    assert sessions.current_or_start("cli") == "s1"
    assert store.current("cli") == "s1"


def test_current_or_start_keeps_returning_the_same_session():
    sessions, _, _ = make_manager("s1", "s2")

    sessions.current_or_start("cli")

    assert sessions.current_or_start("cli") == "s1"


def test_start_new_switches_to_a_fresh_session():
    sessions, _, _ = make_manager("s1", "s2")
    sessions.current_or_start("cli")

    assert sessions.start_new("cli") == "s2"
    assert sessions.current_or_start("cli") == "s2"


def test_owners_have_independent_sessions():
    sessions, _, _ = make_manager("s1", "s2", "s3")
    sessions.current_or_start("cli")
    sessions.current_or_start("line:U1")

    sessions.start_new("cli")

    assert sessions.current_or_start("line:U1") == "s2"


def test_start_new_records_when_the_session_was_created():
    sessions, store, clock = make_manager("s1", "s2")
    sessions.start_new("cli")
    clock.advance(hours=1)
    sessions.start_new("cli")

    assert store.sessions("cli") == [
        SessionInfo("s1", T0),
        SessionInfo("s2", T0 + timedelta(hours=1)),
    ]


def test_default_ids_are_unique():
    store = InMemorySessionStore()
    sessions = SessionManager(store, store)

    assert sessions.start_new("cli") != sessions.start_new("cli")


def test_satisfies_session_lifecycle_port():
    store = InMemorySessionStore()

    assert isinstance(SessionManager(store, store), SessionLifecycle)


# --- retention (D-036) ---

WEEK = RetentionRule("", max_age=timedelta(days=7))


def test_without_rules_nothing_is_removed():
    sessions, store, clock = make_manager("s1", "s2")
    sessions.start_new("cli")
    clock.advance(days=365)

    sessions.start_new("cli")

    assert [info.session_id for info in store.sessions("cli")] == ["s1", "s2"]


def test_sessions_older_than_max_age_are_removed_with_their_messages():
    sessions, store, clock = make_manager("s1", "s2", rules=(WEEK,))
    sessions.start_new("cli")
    store.append("s1", [Message.from_text("user", "old")])
    clock.advance(days=7, seconds=1)

    sessions.start_new("cli")

    assert [info.session_id for info in store.sessions("cli")] == ["s2"]
    assert store.load("s1") == []


def test_sessions_within_max_age_are_kept():
    sessions, store, clock = make_manager("s1", "s2", rules=(WEEK,))
    sessions.start_new("cli")
    clock.advance(days=7)

    sessions.start_new("cli")

    assert [info.session_id for info in store.sessions("cli")] == ["s1", "s2"]


def test_only_the_newest_keep_last_sessions_are_kept():
    rule = RetentionRule("job:", keep_last=2)
    sessions, store, clock = make_manager("s1", "s2", "s3", rules=(rule,))
    for _ in range(3):
        sessions.start_new("job:daily")
        clock.advance(hours=1)

    assert [info.session_id for info in store.sessions("job:daily")] == ["s2", "s3"]


def test_a_session_is_removed_when_either_limit_is_exceeded():
    rule = RetentionRule("job:", max_age=timedelta(days=7), keep_last=5)
    sessions, store, clock = make_manager("s1", "s2", rules=(rule,))
    sessions.start_new("job:daily")
    clock.advance(days=8)

    sessions.start_new("job:daily")

    assert [info.session_id for info in store.sessions("job:daily")] == ["s2"]


def test_the_current_session_is_never_removed():
    sessions, store, clock = make_manager("s1", "s2", rules=(WEEK,))
    sessions.start_new("cli")
    sessions.start_new("web")
    clock.advance(days=30)

    sessions.prune()

    assert store.current("cli") == "s1"
    assert [info.session_id for info in store.sessions("cli")] == ["s1"]


def test_the_first_matching_rule_applies_and_unmatched_owners_are_kept():
    rules = (RetentionRule("job:", keep_last=1),)
    sessions, store, clock = make_manager("s1", "s2", "s3", "s4", rules=rules)
    for owner in ("cli", "cli", "job:daily", "job:daily"):
        sessions.start_new(owner)
        clock.advance(hours=1)

    assert [info.session_id for info in store.sessions("cli")] == ["s1", "s2"]
    assert [info.session_id for info in store.sessions("job:daily")] == ["s4"]


def test_start_new_prunes_every_owner():
    sessions, store, clock = make_manager("s1", "s2", "s3", rules=(WEEK,))
    sessions.start_new("web")
    sessions.start_new("web")
    clock.advance(days=8)

    sessions.start_new("cli")

    assert [info.session_id for info in store.sessions("web")] == ["s2"]


def test_prune_returns_the_removed_session_ids():
    sessions, _, clock = make_manager("s1", "s2", rules=(WEEK,))
    sessions.start_new("cli")
    sessions.start_new("cli")
    clock.advance(days=8)

    assert sessions.prune() == ["s1"]
