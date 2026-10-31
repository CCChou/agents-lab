import io
from collections.abc import Iterator

from agent.adapters.cli import (
    ERROR_PREFIX,
    GOODBYE_MESSAGE,
    PROMPT,
    TOOL_LIMIT_NOTICE,
    WELCOME_MESSAGE,
    run,
)
from agent.adapters.in_memory_store import InMemoryConversationStore
from agent.domain.event import Event, ToolLimitReached, ToolStarted
from agent.domain.message import Message
from agent.domain.request import AgentRequest
from agent.use_cases.chat import Chat


class FakeLLMClient:
    def stream(self, messages: list[Message], tools=None) -> Iterator[str]:
        yield f"echo: {messages[-1].text}"


class ChunkedFakeLLMClient:
    def stream(self, messages: list[Message], tools=None) -> Iterator[str]:
        yield "Hel"
        yield "lo"


class FailsOnceFakeLLMClient:
    def __init__(self) -> None:
        self._failed = False

    def stream(self, messages: list[Message], tools=None) -> Iterator[str]:
        if not self._failed:
            self._failed = True
            raise RuntimeError("connection lost")
        yield "recovered"


class ScriptedChat:
    def __init__(self, events: list[Event]) -> None:
        self._events = events
        self.requests: list[AgentRequest] = []

    def send(self, request: AgentRequest) -> Iterator[Event]:
        self.requests.append(request)
        yield from self._events


def test_run_prints_welcome_message_first_and_goodbye_message_last():
    chat = Chat(FakeLLMClient(), InMemoryConversationStore())
    output = io.StringIO()

    run(chat, [], output)

    assert output.getvalue() == WELCOME_MESSAGE + PROMPT + GOODBYE_MESSAGE


def test_run_sends_each_line_to_chat_and_prints_the_reply():
    chat = Chat(FakeLLMClient(), InMemoryConversationStore())
    output = io.StringIO()

    run(chat, ["hello", "world"], output)

    assert output.getvalue() == (
        WELCOME_MESSAGE
        + PROMPT
        + "echo: hello\n"
        + PROMPT
        + "echo: world\n"
        + PROMPT
        + GOODBYE_MESSAGE
    )


def test_run_writes_each_chunk_as_it_arrives():
    chat = Chat(ChunkedFakeLLMClient(), InMemoryConversationStore())
    output = io.StringIO()

    run(chat, ["hi"], output)

    assert output.getvalue() == WELCOME_MESSAGE + PROMPT + "Hello\n" + PROMPT + GOODBYE_MESSAGE


def test_run_stops_on_exit_command():
    chat = Chat(FakeLLMClient(), InMemoryConversationStore())
    output = io.StringIO()

    run(chat, ["hello", "exit", "should not be sent"], output)

    assert output.getvalue() == (
        WELCOME_MESSAGE + PROMPT + "echo: hello\n" + PROMPT + GOODBYE_MESSAGE
    )


def test_run_skips_blank_lines():
    chat = Chat(FakeLLMClient(), InMemoryConversationStore())
    output = io.StringIO()

    run(chat, ["", "   ", "hi"], output)

    assert output.getvalue() == (
        WELCOME_MESSAGE + PROMPT + PROMPT + PROMPT + "echo: hi\n" + PROMPT + GOODBYE_MESSAGE
    )


def test_run_prints_a_prompt_before_reading_each_line():
    chat = Chat(FakeLLMClient(), InMemoryConversationStore())
    output = io.StringIO()

    run(chat, ["hello"], output)

    assert PROMPT in output.getvalue()


def test_run_sends_every_line_in_the_same_session():
    chat = ScriptedChat([])

    run(chat, ["hello", "world"], io.StringIO())

    assert [r.message for r in chat.requests] == [
        Message.from_text("user", "hello"),
        Message.from_text("user", "world"),
    ]
    assert chat.requests[0].session_id == chat.requests[1].session_id


def test_run_announces_tool_use():
    chat = ScriptedChat([ToolStarted(name="lookup", arguments={"q": "x"})])
    output = io.StringIO()

    run(chat, ["hi"], output)

    assert "[使用工具: lookup arguments={'q': 'x'}]" in output.getvalue()


def test_run_reports_when_the_tool_limit_is_reached():
    chat = ScriptedChat([ToolLimitReached()])
    output = io.StringIO()

    run(chat, ["hi"], output)

    assert TOOL_LIMIT_NOTICE in output.getvalue()


def test_run_reports_llm_errors_and_keeps_the_session_alive():
    chat = Chat(FailsOnceFakeLLMClient(), InMemoryConversationStore())
    output = io.StringIO()

    run(chat, ["hello", "again"], output)

    assert output.getvalue() == (
        WELCOME_MESSAGE
        + PROMPT
        + f"{ERROR_PREFIX}connection lost\n"
        + PROMPT
        + "recovered\n"
        + PROMPT
        + GOODBYE_MESSAGE
    )
