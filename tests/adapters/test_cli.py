import io
from collections.abc import Iterator

from agent.adapters.cli import GOODBYE_MESSAGE, WELCOME_MESSAGE, run
from agent.use_cases.chat import Chat


class FakeLLMClient:
    def stream(self, prompt: str) -> Iterator[str]:
        yield f"echo: {prompt}"


class ChunkedFakeLLMClient:
    def stream(self, prompt: str) -> Iterator[str]:
        yield "Hel"
        yield "lo"


def test_run_prints_welcome_message_first_and_goodbye_message_last():
    chat = Chat(FakeLLMClient())
    output = io.StringIO()

    run(chat, [], output)

    assert output.getvalue() == WELCOME_MESSAGE + GOODBYE_MESSAGE


def test_run_sends_each_line_to_chat_and_prints_the_reply():
    chat = Chat(FakeLLMClient())
    output = io.StringIO()

    run(chat, ["hello", "world"], output)

    assert output.getvalue() == WELCOME_MESSAGE + "echo: hello\necho: world\n" + GOODBYE_MESSAGE


def test_run_writes_each_chunk_as_it_arrives():
    chat = Chat(ChunkedFakeLLMClient())
    output = io.StringIO()

    run(chat, ["hi"], output)

    assert output.getvalue() == WELCOME_MESSAGE + "Hello\n" + GOODBYE_MESSAGE


def test_run_stops_on_exit_command():
    chat = Chat(FakeLLMClient())
    output = io.StringIO()

    run(chat, ["hello", "exit", "should not be sent"], output)

    assert output.getvalue() == WELCOME_MESSAGE + "echo: hello\n" + GOODBYE_MESSAGE


def test_run_skips_blank_lines():
    chat = Chat(FakeLLMClient())
    output = io.StringIO()

    run(chat, ["", "   ", "hi"], output)

    assert output.getvalue() == WELCOME_MESSAGE + "echo: hi\n" + GOODBYE_MESSAGE
