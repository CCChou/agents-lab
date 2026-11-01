from agent.adapters.in_memory_store import InMemoryConversationStore
from agent.domain.agent_spec import AgentSpec
from agent.domain.message import Message
from agent.domain.tool import ToolCall
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


def tool_turn(number: int) -> list[Message]:
    call = ToolCall(id=f"call_{number}", name="read", arguments={"id": number})
    return [
        Message.from_text("user", f"question {number}"),
        Message.from_text("assistant", "", tool_calls=[call]),
        Message.from_text("tool", f"long article {number}", tool_call_id=call.id),
        Message.from_text("assistant", f"answer {number}"),
    ]


def test_build_keeps_tool_results_from_the_latest_turn():
    store = InMemoryConversationStore()
    store.append("s1", tool_turn(1))

    assert ContextBuilder(store).build(AgentSpec(name="test"), "s1") == tool_turn(1)


def test_build_replaces_older_tool_results_and_says_how_to_get_them_back():
    store = InMemoryConversationStore()
    store.append("s1", [*tool_turn(1), *tool_turn(2)])

    context = ContextBuilder(store).build(AgentSpec(name="test"), "s1")

    assert context[4:] == tool_turn(2)
    cleared = context[2]
    assert cleared.tool_call_id == "call_1"
    assert "long article 1" not in cleared.text
    assert "read" in cleared.text
    assert "{'id': 1}" in cleared.text


def test_build_keeps_everything_else_from_older_turns():
    store = InMemoryConversationStore()
    store.append("s1", [*tool_turn(1), *tool_turn(2)])

    context = ContextBuilder(store).build(AgentSpec(name="test"), "s1")

    assert context[:2] == tool_turn(1)[:2]
    assert context[3] == tool_turn(1)[3]


def test_build_does_not_change_the_stored_history():
    store = InMemoryConversationStore()
    history = [*tool_turn(1), *tool_turn(2)]
    store.append("s1", history)

    ContextBuilder(store).build(AgentSpec(name="test"), "s1")

    assert store.load("s1") == history
