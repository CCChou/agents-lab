from datetime import UTC, datetime, timedelta

from agent.adapters.in_memory_store import InMemorySessionStore
from agent.domain.interfaces import ConversationStore, SessionRegistry
from agent.domain.message import Message
from agent.domain.session import SessionInfo


def test_satisfies_conversation_store_port():
    assert isinstance(InMemorySessionStore(), ConversationStore)


def test_load_returns_empty_list_for_unknown_session():
    assert InMemorySessionStore().load("unknown") == []


def test_load_returns_appended_messages_in_order():
    store = InMemorySessionStore()
    first = Message.from_text("user", "hi")
    second = Message.from_text("assistant", "hello")

    store.append("s1", [first])
    store.append("s1", [second])

    assert store.load("s1") == [first, second]


def test_sessions_are_isolated():
    store = InMemorySessionStore()

    store.append("s1", [Message.from_text("user", "hi")])

    assert store.load("s2") == []


def test_changing_the_loaded_list_does_not_change_the_store():
    store = InMemorySessionStore()
    store.append("s1", [Message.from_text("user", "hi")])

    store.load("s1").clear()

    assert len(store.load("s1")) == 1


def test_satisfies_session_registry_port():
    assert isinstance(InMemorySessionStore(), SessionRegistry)


def test_current_is_none_for_an_unknown_owner():
    assert InMemorySessionStore().current("cli") is None


def test_set_current_changes_the_current_session_of_that_owner_only():
    store = InMemorySessionStore()

    store.set_current("cli", "s1")
    store.set_current("cli", "s2")
    store.set_current("line:U1", "s3")

    assert store.current("cli") == "s2"
    assert store.current("line:U1") == "s3"


def test_switching_the_current_session_keeps_the_old_messages():
    store = InMemorySessionStore()
    store.set_current("cli", "s1")
    store.append("s1", [Message.from_text("user", "hi")])

    store.set_current("cli", "s2")

    assert store.load("s2") == []
    assert store.load("s1") == [Message.from_text("user", "hi")]


T0 = datetime(2026, 11, 1, tzinfo=UTC)


def test_sessions_lists_the_sessions_of_an_owner_oldest_first():
    store = InMemorySessionStore()
    store.add("cli", "s2", T0 + timedelta(hours=1))
    store.add("cli", "s1", T0)
    store.add("web", "s3", T0)

    assert store.sessions("cli") == [
        SessionInfo("s1", T0),
        SessionInfo("s2", T0 + timedelta(hours=1)),
    ]
    assert store.sessions("nobody") == []


def test_owners_lists_every_owner_with_sessions():
    store = InMemorySessionStore()
    store.add("cli", "s1", T0)
    store.add("job:daily", "s2", T0)

    assert sorted(store.owners()) == ["cli", "job:daily"]


def test_remove_forgets_only_that_session():
    store = InMemorySessionStore()
    store.add("cli", "s1", T0)
    store.add("cli", "s2", T0)

    store.remove("cli", "s1")

    assert store.sessions("cli") == [SessionInfo("s2", T0)]


def test_removing_the_last_session_forgets_the_owner():
    store = InMemorySessionStore()
    store.add("cli", "s1", T0)

    store.remove("cli", "s1")

    assert store.owners() == []


def test_delete_drops_the_messages_of_that_session_only():
    store = InMemorySessionStore()
    store.append("s1", [Message.from_text("user", "hi")])
    store.append("s2", [Message.from_text("user", "keep")])

    store.delete("s1")

    assert store.load("s1") == []
    assert store.load("s2") == [Message.from_text("user", "keep")]
