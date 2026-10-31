from collections.abc import Iterator
from typing import Any

from agent.domain.event import TextDelta, ToolLimitReached, ToolStarted
from agent.domain.interfaces import LLMClient
from agent.domain.message import Message
from agent.domain.tool import Tool, ToolCall
from agent.use_cases.chat import Chat


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

    def run(self, arguments: dict[str, Any]) -> str:
        self.received_arguments = arguments
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def test_fake_satisfies_llm_client_port():
    assert isinstance(FakeLLMClient(replies=[]), LLMClient)


def test_send_forwards_the_message_and_streams_each_llm_chunk():
    llm_client = FakeLLMClient(replies=[["hello ", "there"]])
    chat = Chat(llm_client)

    events = list(chat.send("hi"))

    assert events == [TextDelta("hello "), TextDelta("there")]
    assert llm_client.received_messages_per_call == [[Message.from_text("user", "hi")]]


def test_send_yields_text_before_the_llm_finishes():
    class StopsAfterFirstChunk:
        def stream(self, messages, tools=None):
            yield "first"
            raise AssertionError("send read past the first chunk")

    events = Chat(StopsAfterFirstChunk()).send("hi")

    assert next(events) == TextDelta("first")


def test_send_records_the_joined_reply_in_history():
    llm_client = FakeLLMClient(replies=[["hello ", "there"], ["ok"]])
    chat = Chat(llm_client)

    list(chat.send("hi"))
    list(chat.send("again"))

    assert llm_client.received_messages_per_call[1][1] == Message.from_text(
        "assistant", "hello there"
    )


def test_send_includes_prior_turns_in_the_next_request():
    llm_client = FakeLLMClient(replies=[["hi there"], ["I'm good, thanks"]])
    chat = Chat(llm_client)

    list(chat.send("hello"))
    list(chat.send("how are you"))

    assert llm_client.received_messages_per_call[1] == [
        Message.from_text("user", "hello"),
        Message.from_text("assistant", "hi there"),
        Message.from_text("user", "how are you"),
    ]


def test_send_prepends_system_prompt_when_configured():
    llm_client = FakeLLMClient(replies=[["hi"]])
    chat = Chat(llm_client, system_prompt="You are terse.")

    list(chat.send("hello"))

    assert llm_client.received_messages_per_call[0] == [
        Message.from_text("system", "You are terse."),
        Message.from_text("user", "hello"),
    ]


def test_system_prompt_is_not_repeated_across_turns():
    llm_client = FakeLLMClient(replies=[["hi there"], ["I'm good"]])
    chat = Chat(llm_client, system_prompt="Be terse.")

    list(chat.send("hello"))
    list(chat.send("how are you"))

    second_call_messages = llm_client.received_messages_per_call[1]
    system_messages = [m for m in second_call_messages if m.role == "system"]
    assert system_messages == [Message.from_text("system", "Be terse.")]


def test_no_system_message_when_system_prompt_not_given():
    llm_client = FakeLLMClient(replies=[["hi"]])
    chat = Chat(llm_client)

    list(chat.send("hello"))

    assert llm_client.received_messages_per_call[0] == [Message.from_text("user", "hello")]


def test_send_passes_no_tools_when_none_configured():
    llm_client = FakeLLMClient(replies=[["hi"]])
    chat = Chat(llm_client)

    list(chat.send("hello"))

    assert llm_client.received_tools_per_call == [None]


def test_send_passes_configured_tools_to_the_llm_client():
    llm_client = FakeLLMClient(replies=[["hi"]])
    tool = FakeTool(name="lookup")
    chat = Chat(llm_client, tools=[tool])

    list(chat.send("hello"))

    assert llm_client.received_tools_per_call == [[tool]]


def test_send_executes_tool_call_and_feeds_result_back_to_the_llm():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={"q": "weather"})
    llm_client = FakeLLMClient(replies=[[tool_call], ["it is sunny"]])
    tool = FakeTool(name="lookup", result="72F and clear")
    chat = Chat(llm_client, tools=[tool])

    events = list(chat.send("what's the weather"))

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
    chat = Chat(llm_client, tools=[tool])

    list(chat.send("hi"))

    second_call_messages = llm_client.received_messages_per_call[1]
    assistant_message = next(m for m in second_call_messages if m.role == "assistant")
    assert assistant_message.tool_calls == [tool_call]


def test_send_announces_tool_call_before_executing_it():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={"q": "weather"})
    llm_client = FakeLLMClient(replies=[[tool_call], ["it is sunny"]])
    tool = FakeTool(name="lookup", result="72F and clear")
    chat = Chat(llm_client, tools=[tool])

    events = chat.send("what's the weather")

    assert next(events) == ToolStarted(name="lookup", arguments={"q": "weather"})
    assert tool.received_arguments is None


def test_send_reports_unknown_tool_back_to_the_llm_instead_of_raising():
    tool_call = ToolCall(id="call_1", name="nonexistent", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call], ["fallback answer"]])
    chat = Chat(llm_client, tools=[])

    list(chat.send("do something"))

    tool_result = llm_client.received_messages_per_call[1][-1]
    assert tool_result.role == "tool"
    assert "nonexistent" in tool_result.text


def test_send_stops_after_max_tool_iterations_instead_of_looping_forever():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call]] * 3 + [["partial answer"]])
    tool = FakeTool(name="lookup", result="r")
    chat = Chat(llm_client, tools=[tool], max_tool_iterations=3)

    list(chat.send("do something"))

    assert len(llm_client.received_messages_per_call) == 4


def test_send_asks_for_a_final_answer_without_tools_after_reaching_the_limit():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call], ["partial answer"]])
    tool = FakeTool(name="lookup", result="r")
    chat = Chat(llm_client, tools=[tool], max_tool_iterations=1)

    events = list(chat.send("do something"))

    assert llm_client.received_tools_per_call == [[tool], None]
    assert TextDelta("partial answer") in events
    assert ToolLimitReached() not in events


def test_tool_call_at_the_limit_gets_a_result_without_being_executed():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={"q": "x"})
    llm_client = FakeLLMClient(replies=[[tool_call], ["partial answer"]])
    tool = FakeTool(name="lookup", result="r")
    chat = Chat(llm_client, tools=[tool], max_tool_iterations=1)

    list(chat.send("do something"))

    assert tool.received_arguments is None
    tool_result = llm_client.received_messages_per_call[1][-1]
    assert tool_result.role == "tool"
    assert tool_result.tool_call_id == "call_1"
    assert "上限" in tool_result.text


def test_every_tool_call_has_a_result_in_the_next_turn_after_reaching_the_limit():
    first_call = ToolCall(id="call_1", name="lookup", arguments={})
    second_call = ToolCall(id="call_2", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[first_call, second_call], ["partial"], ["next answer"]])
    chat = Chat(llm_client, tools=[FakeTool(name="lookup")], max_tool_iterations=1)

    list(chat.send("do something"))
    list(chat.send("and now"))

    next_turn_messages = llm_client.received_messages_per_call[2]
    answered_ids = {m.tool_call_id for m in next_turn_messages if m.role == "tool"}
    assert answered_ids == {"call_1", "call_2"}


def test_tool_call_in_the_final_answer_still_gets_a_result_in_the_next_turn():
    first_call = ToolCall(id="call_1", name="lookup", arguments={})
    unexpected_call = ToolCall(id="call_2", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[first_call], ["partial", unexpected_call], ["next"]])
    chat = Chat(llm_client, tools=[FakeTool(name="lookup")], max_tool_iterations=1)

    list(chat.send("do something"))
    list(chat.send("and now"))

    next_turn_messages = llm_client.received_messages_per_call[2]
    answered_ids = {m.tool_call_id for m in next_turn_messages if m.role == "tool"}
    assert answered_ids == {"call_1", "call_2"}


def test_send_reports_the_limit_when_the_final_answer_request_fails():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call], RuntimeError("tools required")])
    chat = Chat(llm_client, tools=[FakeTool(name="lookup")], max_tool_iterations=1)

    events = list(chat.send("do something"))

    assert ToolLimitReached() in events


def test_send_reports_the_limit_when_the_final_answer_is_empty():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call], []])
    chat = Chat(llm_client, tools=[FakeTool(name="lookup")], max_tool_iterations=1)

    events = list(chat.send("do something"))

    assert ToolLimitReached() in events


def test_send_reports_tool_execution_error_back_to_the_llm_instead_of_raising():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={})
    llm_client = FakeLLMClient(replies=[[tool_call], ["fallback answer"]])
    tool = FakeTool(name="lookup", result=RuntimeError("boom"))
    chat = Chat(llm_client, tools=[tool])

    list(chat.send("do something"))

    tool_result = llm_client.received_messages_per_call[1][-1]
    assert tool_result.role == "tool"
    assert "boom" in tool_result.text
