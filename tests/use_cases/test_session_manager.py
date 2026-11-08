from agent.adapters.in_memory_store import InMemorySessionStore
from agent.use_cases.session_manager import SessionManager


def make_manager(*ids: str) -> tuple[SessionManager, InMemorySessionStore]:
    store = InMemorySessionStore()
    return SessionManager(store, new_id=iter(ids).__next__), store


def test_current_or_start_starts_a_session_on_first_use():
    sessions, store = make_manager("s1")

    assert sessions.current_or_start("cli") == "s1"
    assert store.current("cli") == "s1"


def test_current_or_start_keeps_returning_the_same_session():
    sessions, _ = make_manager("s1", "s2")

    sessions.current_or_start("cli")

    assert sessions.current_or_start("cli") == "s1"


def test_start_new_switches_to_a_fresh_session():
    sessions, _ = make_manager("s1", "s2")
    sessions.current_or_start("cli")

    assert sessions.start_new("cli") == "s2"
    assert sessions.current_or_start("cli") == "s2"


def test_owners_have_independent_sessions():
    sessions, _ = make_manager("s1", "s2", "s3")
    sessions.current_or_start("cli")
    sessions.current_or_start("line:U1")

    sessions.start_new("cli")

    assert sessions.current_or_start("line:U1") == "s2"


def test_default_ids_are_unique():
    sessions = SessionManager(InMemorySessionStore())

    assert sessions.start_new("cli") != sessions.start_new("cli")
