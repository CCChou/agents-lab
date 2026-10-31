from agent.adapters.in_memory_store import InMemoryConversationStore
from agent.domain.interfaces import ConversationStore
from agent.domain.message import Message


def test_satisfies_conversation_store_port():
    assert isinstance(InMemoryConversationStore(), ConversationStore)


def test_load_returns_empty_list_for_unknown_session():
    assert InMemoryConversationStore().load("unknown") == []


def test_load_returns_appended_messages_in_order():
    store = InMemoryConversationStore()
    first = Message.from_text("user", "hi")
    second = Message.from_text("assistant", "hello")

    store.append("s1", [first])
    store.append("s1", [second])

    assert store.load("s1") == [first, second]


def test_sessions_are_isolated():
    store = InMemoryConversationStore()

    store.append("s1", [Message.from_text("user", "hi")])

    assert store.load("s2") == []


def test_changing_the_loaded_list_does_not_change_the_store():
    store = InMemoryConversationStore()
    store.append("s1", [Message.from_text("user", "hi")])

    store.load("s1").clear()

    assert len(store.load("s1")) == 1
