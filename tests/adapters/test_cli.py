import io
from collections.abc import Iterator

from agent.adapters.cli import GOODBYE_MESSAGE, PROMPT, WELCOME_MESSAGE, run
from agent.domain.message import Message
from agent.use_cases.chat import Chat


class FakeLLMClient:
    def stream(self, messages: list[Message], tools=None) -> Iterator[str]:
        yield f"echo: {messages[-1].content}"


class ChunkedFakeLLMClient:
    def stream(self, messages: list[Message], tools=None) -> Iterator[str]:
        yield "Hel"
        yield "lo"


def test_run_prints_welcome_message_first_and_goodbye_message_last():
    chat = Chat(FakeLLMClient())
    output = io.StringIO()

    run(chat, [], output)

    assert output.getvalue() == WELCOME_MESSAGE + PROMPT + GOODBYE_MESSAGE


def test_run_sends_each_line_to_chat_and_prints_the_reply():
    chat = Chat(FakeLLMClient())
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
    chat = Chat(ChunkedFakeLLMClient())
    output = io.StringIO()

    run(chat, ["hi"], output)

    assert output.getvalue() == WELCOME_MESSAGE + PROMPT + "Hello\n" + PROMPT + GOODBYE_MESSAGE


def test_run_stops_on_exit_command():
    chat = Chat(FakeLLMClient())
    output = io.StringIO()

    run(chat, ["hello", "exit", "should not be sent"], output)

    assert output.getvalue() == (
        WELCOME_MESSAGE + PROMPT + "echo: hello\n" + PROMPT + GOODBYE_MESSAGE
    )


def test_run_skips_blank_lines():
    chat = Chat(FakeLLMClient())
    output = io.StringIO()

    run(chat, ["", "   ", "hi"], output)

    assert output.getvalue() == (
        WELCOME_MESSAGE + PROMPT + PROMPT + PROMPT + "echo: hi\n" + PROMPT + GOODBYE_MESSAGE
    )


def test_run_prints_a_prompt_before_reading_each_line():
    chat = Chat(FakeLLMClient())
    output = io.StringIO()

    run(chat, ["hello"], output)

    assert PROMPT in output.getvalue()


def test_run_sends_each_reply_chunk_through_the_given_renderer():
    chat = Chat(FakeLLMClient())
    output = io.StringIO()
    rendered_calls: list[tuple[str, io.StringIO]] = []

    def fake_renderer(text: str, out: io.StringIO) -> None:
        rendered_calls.append((text, out))
        out.write(f"<<{text}>>")

    run(chat, ["hello"], output, render=fake_renderer)

    assert rendered_calls == [("echo: hello", output)]
    assert "<<echo: hello>>" in output.getvalue()
