from collections.abc import Iterator
from typing import Any

import pytest

from agent.adapters.in_memory_store import InMemoryConversationStore
from agent.domain.agent_spec import AgentSpec
from agent.domain.event import TextDelta, ToolLimitReached, ToolStarted
from agent.domain.interfaces import Agent, LLMClient
from agent.domain.message import Message
from agent.domain.request import AgentRequest
from agent.domain.tool import Tool, ToolCall
from agent.use_cases.context_builder import ContextBuilder
from agent.use_cases.loop_agent import LoopAgent
from agent.use_cases.tool_registry import ToolRegistry


def make_agent(
    llm_client,
    store=None,
    *,
    system_prompt: str | None = None,
    tools: list[Tool] | None = None,
    max_tool_iterations: int = 5,
    tool_call_limits: dict[str, int] | None = None,
) -> LoopAgent:
    store = store or InMemoryConversationStore()
    tools = tools or []
    spec = AgentSpec(
        name="test",
        system_prompt=system_prompt,
        tools=tuple(tool.name for tool in tools),
        max_tool_iterations=max_tool_iterations,
        tool_call_limits=tool_call_limits or {},
    )
    return LoopAgent(spec, llm_client, store, ContextBuilder(store), ToolRegistry(tools))


def request(text: str, session_id: str = "s1") -> AgentRequest:
    return AgentRequest(session_id=session_id, message=Message.from_text("user", text))


class FakeLLMClient:
    def __init__(self, replies: list[list[str | ToolCall] | Exception]) -> None:
        self._replies = iter(replies)
        self.received_messages_per_call: list[list[Message]] = []
        self.received_tools_per_call: list[list[Tool] | None] = []

    def stream(
        self, messages: list[Message], tools: list[Tool] | None = None
    ) -> Iterator[str | ToolCall]:
        self.received_messages_per_call.append(messages)
        self.received_tools_per_call.append(tools)
        reply = next(self._replies)
        if isinstance(reply, Exception):
            raise reply
        yield from reply


class FakeTool:
    def __init__(self, name: str, result: str | Exception = "tool result") -> None:
        self.name = name
        self.description = "a fake tool"
        self.parameters_schema: dict[str, Any] = {"type": "object", "properties": {}}
        self._result = result
        self.received_arguments: dict[str, Any] | None = None
        self.run_count = 0

    def run(self, arguments: dict[str, Any]) -> str:
        self.received_arguments = arguments
        self.run_count += 1
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def test_fake_satisfies_llm_client_port():
    assert isinstance(FakeLLMClient(replies=[]), LLMClient)


def test_run_forwards_the_message_and_streams_each_llm_chunk():
    llm_client = FakeLLMClient(replies=[["hello ", "there"]])
    agent = make_agent(llm_client)

    events = list(agent.run(request("hi")))

    assert events == [TextDelta("hello "), TextDelta("there")]
    assert llm_client.received_messages_per_call == [[Message.from_text("user", "hi")]]


def test_run_yields_text_before_the_llm_finishes():
    class StopsAfterFirstChunk:
        def stream(self, messages, tools=None):
            yield "first"
            raise AssertionError("run read past the first chunk")

    events = make_agent(StopsAfterFirstChunk()).run(request("hi"))

    assert next(events) == TextDelta("first")


def test_run_records_the_joined_reply_in_history():
    llm_client = FakeLLMClient(replies=[["hello ", "there"], ["ok"]])
    agent = make_agent(llm_client)

    list(agent.run(request("hi")))
    list(agent.run(request("again")))

    assert llm_client.received_messages_per_call[1][1] == Message.from_text(
        "assistant", "hello there"
    )


def test_run_includes_prior_turns_in_the_next_request():
    llm_client = FakeLLMClient(replies=[["hi there"], ["I'm good, thanks"]])
    agent = make_agent(llm_client)

    list(agent.run(request("hello")))
    list(agent.run(request("how are you")))

    assert llm_client.received_messages_per_call[1] == [
        Message.from_text("user", "hello"),
        Message.from_text("assistant", "hi there"),
        Message.from_text("user", "how are you"),
    ]


def test_run_prepends_system_prompt_when_configured():
    llm_client = FakeLLMClient(replies=[["hi"]])
    agent = make_agent(llm_client, system_prompt="You are terse.")

    list(agent.run(request("hello")))

    assert llm_client.received_messages_per_call[0] == [
        Message.from_text("system", "You are terse."),
        Message.from_text("user", "hello"),
    ]


def test_system_prompt_is_not_repeated_across_turns():
    llm_client = FakeLLMClient(replies=[["hi there"], ["I'm good"]])
    agent = make_agent(llm_client, system_prompt="Be terse.")

    list(agent.run(request("hello")))
    list(agent.run(request("how are you")))

    second_call_messages = llm_client.received_messages_per_call[1]
    system_messages = [m for m in second_call_messages if m.role == "system"]
    assert system_messages == [Message.from_text("system", "Be terse.")]


def test_no_system_message_when_system_prompt_not_given():
    llm_client = FakeLLMClient(replies=[["hi"]])
    agent = make_agent(llm_client)

    list(agent.run(request("hello")))

    assert llm_client.received_messages_per_call[0] == [Message.from_text("user", "hello")]


def test_run_passes_no_tools_when_none_configured():
    llm_client = FakeLLMClient(replies=[["hi"]])
    agent = make_agent(llm_client)

    list(agent.run(request("hello")))

    assert llm_client.received_tools_per_call == [None]


def test_run_passes_configured_tools_to_the_llm_client():
    llm_client = FakeLLMClient(replies=[["hi"]])
    tool = FakeTool(name="lookup")
    agent = make_agent(llm_client, tools=[tool])

    list(agent.run(request("hello")))

    assert llm_client.received_tools_per_call == [[tool]]


def test_run_executes_tool_call_and_feeds_result_back_to_the_llm():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={"q": "weather"})
    llm_client = FakeLLMClient(replies=[[tool_call], ["it is sunny"]])
    tool = FakeTool(name="lookup", result="72F and clear")
    agent = make_agent(llm_client, tools=[tool])

    events = list(agent.run(request("what's the weather")))

    assert tool.received_arguments == {"q": "weather"}
    assert TextDelta("it is sunny") in events
    second_call_messages = llm_client.received_messages_per_call[1]
    assert second_call_messages[-1] == Message.from_text(
        "tool", "72F and clear", tool_call_id="call_1"
    )


def test_assistant_message_with_tool_call_is_recorded_in_history():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={"q": "x"})
    llm_client = FakeLLMClient(replies=[[tool_call], ["final"]])
    tool = FakeTool(name="lookup", result="r")
    agent = make_agent(llm_client, tools=[tool])

    list(agent.run(request("hi")))

    second_call_messages = llm_client.received_messages_per_call[1]
    assistant_message = next(m for m in second_call_messages if m.role == "assistant")
    assert assistant_message.tool_calls == [tool_call]


def test_run_announces_tool_call_before_executing_it():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={"q": "weather"})
    llm_client = FakeLLMClient(replies=[[tool_call], ["it is sunny"]])
    tool = FakeTool(name="lookup", result="72F and clear")
    agent = make_agent(llm_client, tools=[tool])

    events = agent.run(request("what's the weather"))

    assert next(events) == ToolStarted(name="lookup", arguments={"q": "weather"})
    assert tool.received_arguments is None


def test_run_reports_unknown_tool_back_to_the_llm_instead_of_raising():
    tool_call = ToolCall(id="call_1", name="nonexistent", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call], ["fallback answer"]])
    agent = make_agent(llm_client, tools=[])

    list(agent.run(request("do something")))

    tool_result = llm_client.received_messages_per_call[1][-1]
    assert tool_result.role == "tool"
    assert "nonexistent" in tool_result.text


def test_run_stops_after_max_tool_iterations_instead_of_looping_forever():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call]] * 3 + [["partial answer"]])
    tool = FakeTool(name="lookup", result="r")
    agent = make_agent(llm_client, tools=[tool], max_tool_iterations=3)

    list(agent.run(request("do something")))

    assert len(llm_client.received_messages_per_call) == 4


def test_run_asks_for_a_final_answer_without_tools_after_reaching_the_limit():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call], ["partial answer"]])
    tool = FakeTool(name="lookup", result="r")
    agent = make_agent(llm_client, tools=[tool], max_tool_iterations=1)

    events = list(agent.run(request("do something")))

    assert llm_client.received_tools_per_call == [[tool], None]
    assert TextDelta("partial answer") in events
    assert ToolLimitReached() not in events


def test_tool_call_at_the_limit_gets_a_result_without_being_executed():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={"q": "x"})
    llm_client = FakeLLMClient(replies=[[tool_call], ["partial answer"]])
    tool = FakeTool(name="lookup", result="r")
    agent = make_agent(llm_client, tools=[tool], max_tool_iterations=1)

    list(agent.run(request("do something")))

    assert tool.received_arguments is None
    tool_result = llm_client.received_messages_per_call[1][-1]
    assert tool_result.role == "tool"
    assert tool_result.tool_call_id == "call_1"
    assert "上限" in tool_result.text


def _call(call_id: str, name: str = "lookup") -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments={})


def test_tool_call_limit_stops_extra_calls_in_the_same_reply():
    llm_client = FakeLLMClient(replies=[[_call("c1"), _call("c2"), _call("c3")], ["answer"]])
    tool = FakeTool(name="lookup")
    agent = make_agent(llm_client, tools=[tool], tool_call_limits={"lookup": 2})

    events = list(agent.run(request("do something")))

    assert tool.run_count == 2
    assert sum(isinstance(event, ToolStarted) for event in events) == 2
    results = [m for m in llm_client.received_messages_per_call[1] if m.role == "tool"]
    assert [m.tool_call_id for m in results] == ["c1", "c2", "c3"]
    assert "未執行" in results[2].text
    assert "上限" in results[2].text


def test_tool_call_limit_counts_across_iterations_of_one_turn():
    llm_client = FakeLLMClient(replies=[[_call("c1")], [_call("c2")], [_call("c3")], ["answer"]])
    tool = FakeTool(name="lookup")
    agent = make_agent(llm_client, tools=[tool], tool_call_limits={"lookup": 2})

    list(agent.run(request("do something")))

    assert tool.run_count == 2


def test_tool_call_limit_resets_for_the_next_user_message():
    llm_client = FakeLLMClient(replies=[[_call("c1")], ["a"], [_call("c2")], ["b"]])
    tool = FakeTool(name="lookup")
    agent = make_agent(llm_client, tools=[tool], tool_call_limits={"lookup": 1})

    list(agent.run(request("first")))
    list(agent.run(request("second")))

    assert tool.run_count == 2


def test_tool_call_limit_applies_only_to_the_named_tool():
    llm_client = FakeLLMClient(replies=[[_call("c1", "other"), _call("c2", "other")], ["answer"]])
    limited = FakeTool(name="lookup")
    other = FakeTool(name="other")
    agent = make_agent(llm_client, tools=[limited, other], tool_call_limits={"lookup": 1})

    list(agent.run(request("do something")))

    assert other.run_count == 2


def test_every_tool_call_has_a_result_in_the_next_turn_after_reaching_the_limit():
    first_call = ToolCall(id="call_1", name="lookup", arguments={})
    second_call = ToolCall(id="call_2", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[first_call, second_call], ["partial"], ["next answer"]])
    agent = make_agent(llm_client, tools=[FakeTool(name="lookup")], max_tool_iterations=1)

    list(agent.run(request("do something")))
    list(agent.run(request("and now")))

    next_turn_messages = llm_client.received_messages_per_call[2]
    answered_ids = {m.tool_call_id for m in next_turn_messages if m.role == "tool"}
    assert answered_ids == {"call_1", "call_2"}


def test_tool_call_in_the_final_answer_still_gets_a_result_in_the_next_turn():
    first_call = ToolCall(id="call_1", name="lookup", arguments={})
    unexpected_call = ToolCall(id="call_2", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[first_call], ["partial", unexpected_call], ["next"]])
    agent = make_agent(llm_client, tools=[FakeTool(name="lookup")], max_tool_iterations=1)

    list(agent.run(request("do something")))
    list(agent.run(request("and now")))

    next_turn_messages = llm_client.received_messages_per_call[2]
    answered_ids = {m.tool_call_id for m in next_turn_messages if m.role == "tool"}
    assert answered_ids == {"call_1", "call_2"}


def test_run_reports_the_limit_when_the_final_answer_request_fails():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call], RuntimeError("tools required")])
    agent = make_agent(llm_client, tools=[FakeTool(name="lookup")], max_tool_iterations=1)

    events = list(agent.run(request("do something")))

    assert ToolLimitReached() in events


def test_run_reports_the_limit_when_the_final_answer_is_empty():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call], []])
    agent = make_agent(llm_client, tools=[FakeTool(name="lookup")], max_tool_iterations=1)

    events = list(agent.run(request("do something")))

    assert ToolLimitReached() in events


def test_run_reports_tool_execution_error_back_to_the_llm_instead_of_raising():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call], ["fallback answer"]])
    tool = FakeTool(name="lookup", result=RuntimeError("boom"))
    agent = make_agent(llm_client, tools=[tool])

    list(agent.run(request("do something")))

    tool_result = llm_client.received_messages_per_call[1][-1]
    assert tool_result.role == "tool"
    assert "boom" in tool_result.text


def test_sessions_do_not_share_history():
    llm_client = FakeLLMClient(replies=[["first"], ["second"]])
    agent = make_agent(llm_client)

    list(agent.run(request("hello", session_id="s1")))
    list(agent.run(request("hi", session_id="s2")))

    assert llm_client.received_messages_per_call[1] == [Message.from_text("user", "hi")]


def test_system_prompt_is_sent_but_not_stored():
    llm_client = FakeLLMClient(replies=[["hi"]])
    store = InMemoryConversationStore()
    agent = make_agent(llm_client, store, system_prompt="Be terse.")

    list(agent.run(request("hello")))

    assert all(message.role != "system" for message in store.load("s1"))


def test_failed_turn_is_not_stored():
    llm_client = FakeLLMClient(replies=[RuntimeError("connection lost"), ["ok"]])
    agent = make_agent(llm_client)

    with pytest.raises(RuntimeError):
        list(agent.run(request("lost")))
    list(agent.run(request("retry")))

    assert llm_client.received_messages_per_call[1] == [Message.from_text("user", "retry")]


def test_turn_that_fails_after_a_tool_call_is_not_stored():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call], RuntimeError("connection lost")])
    store = InMemoryConversationStore()
    agent = make_agent(llm_client, store, tools=[FakeTool(name="lookup")])

    with pytest.raises(RuntimeError):
        list(agent.run(request("do something")))

    assert store.load("s1") == []


def test_turn_that_ends_with_the_limit_notice_is_stored():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call], RuntimeError("tools required")])
    store = InMemoryConversationStore()
    agent = make_agent(llm_client, store, tools=[FakeTool(name="lookup")], max_tool_iterations=1)

    list(agent.run(request("do something")))

    assert [message.role for message in store.load("s1")] == ["user", "assistant", "tool"]


def test_satisfies_agent_port():
    agent = make_agent(FakeLLMClient(replies=[]))

    assert isinstance(agent, Agent)
    assert agent.name == "test"


def test_only_tools_listed_in_the_spec_are_available():
    tool_call = ToolCall(id="call_1", name="secret", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call], ["done"]])
    lookup, secret = FakeTool(name="lookup"), FakeTool(name="secret")
    store = InMemoryConversationStore()
    spec = AgentSpec(name="test", tools=("lookup",))
    agent = LoopAgent(
        spec, llm_client, store, ContextBuilder(store), ToolRegistry([lookup, secret])
    )

    list(agent.run(request("do something")))

    assert llm_client.received_tools_per_call[0] == [lookup]
    assert secret.received_arguments is None


def test_unknown_tool_in_the_spec_fails_at_construction():
    store = InMemoryConversationStore()
    spec = AgentSpec(name="test", tools=("missing",))

    with pytest.raises(ValueError, match="missing"):
        LoopAgent(spec, FakeLLMClient(replies=[]), store, ContextBuilder(store), ToolRegistry([]))
