from agent.adapters.in_memory_store import InMemoryConversationStore
from agent.domain.agent_spec import AgentSpec
from agent.domain.message import Message
from agent.use_cases.context_builder import ContextBuilder


def test_build_returns_stored_history():
    store = InMemoryConversationStore()
    history = [Message.from_text("user", "hi"), Message.from_text("assistant", "hello")]
    store.append("s1", history)

    assert ContextBuilder(store).build(AgentSpec(name="test"), "s1") == history


def test_build_puts_the_system_prompt_first():
    store = InMemoryConversationStore()
    store.append("s1", [Message.from_text("user", "hi")])
    spec = AgentSpec(name="test", system_prompt="Be terse.")

    assert ContextBuilder(store).build(spec, "s1") == [
        Message.from_text("system", "Be terse."),
        Message.from_text("user", "hi"),
    ]


def test_build_is_empty_for_a_new_session_without_system_prompt():
    builder = ContextBuilder(InMemoryConversationStore())

    assert builder.build(AgentSpec(name="test"), "new") == []
