import io

from agent.adapters.cli import run
from agent.use_cases.chat import Chat


class FakeLLMClient:
    def complete(self, prompt: str) -> str:
        return f"echo: {prompt}"


def test_run_sends_each_line_to_chat_and_prints_the_reply():
    chat = Chat(FakeLLMClient())
    output = io.StringIO()

    run(chat, ["hello", "world"], output)

    assert output.getvalue() == "echo: hello\necho: world\n"


def test_run_stops_on_exit_command():
    chat = Chat(FakeLLMClient())
    output = io.StringIO()

    run(chat, ["hello", "exit", "should not be sent"], output)

    assert output.getvalue() == "echo: hello\n"


def test_run_skips_blank_lines():
    chat = Chat(FakeLLMClient())
    output = io.StringIO()

    run(chat, ["", "   ", "hi"], output)

    assert output.getvalue() == "echo: hi\n"
