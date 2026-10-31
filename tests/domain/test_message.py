from agent.domain.message import Message, TextPart
from agent.domain.tool import ToolCall


def test_from_text_wraps_the_text_in_a_text_part():
    message = Message.from_text("user", "hi")

    assert message == Message(role="user", content=[TextPart("hi")])


def test_from_text_keeps_tool_fields():
    tool_call = ToolCall(id="call_1", name="lookup", arguments={})

    assistant = Message.from_text("assistant", "checking", tool_calls=[tool_call])
    tool_result = Message.from_text("tool", "done", tool_call_id="call_1")

    assert assistant.tool_calls == [tool_call]
    assert tool_result.tool_call_id == "call_1"


def test_from_text_with_empty_text_has_no_parts():
    assert Message.from_text("assistant", "").content == []


def test_text_joins_all_text_parts():
    message = Message(role="user", content=[TextPart("hello "), TextPart("there")])

    assert message.text == "hello there"


def test_text_is_empty_when_there_are_no_parts():
    assert Message(role="assistant", content=[]).text == ""
