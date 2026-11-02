import io
from collections.abc import Iterator

from rich.console import Console

from agent.adapters.cli import (
    ERROR_PREFIX,
    GOODBYE_MESSAGE,
    PROMPT,
    TOOL_LIMIT_NOTICE,
    WELCOME_MESSAGE,
    MarkdownBlockWriter,
    prompt_lines,
    run,
)
from agent.adapters.in_memory_store import InMemoryConversationStore
from agent.domain.agent_spec import AgentSpec
from agent.domain.event import Event, TextDelta, ToolLimitReached, ToolStarted
from agent.domain.message import Message
from agent.domain.request import AgentRequest
from agent.use_cases.context_builder import ContextBuilder
from agent.use_cases.loop_agent import LoopAgent
from agent.use_cases.tool_registry import ToolRegistry


def make_agent(llm_client) -> LoopAgent:
    store = InMemoryConversationStore()
    spec = AgentSpec(name="test")
    return LoopAgent(spec, llm_client, store, ContextBuilder(store), ToolRegistry([]))


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


class ScriptedAgent:
    name = "scripted"

    def __init__(self, events: list[Event]) -> None:
        self._events = events
        self.requests: list[AgentRequest] = []

    def run(self, request: AgentRequest) -> Iterator[Event]:
        self.requests.append(request)
        yield from self._events


def test_run_prints_welcome_message_first_and_goodbye_message_last():
    agent = make_agent(FakeLLMClient())
    output = io.StringIO()

    run(agent, [], output)

    assert output.getvalue() == WELCOME_MESSAGE + PROMPT + GOODBYE_MESSAGE


def test_run_sends_each_line_to_chat_and_prints_the_reply():
    agent = make_agent(FakeLLMClient())
    output = io.StringIO()

    run(agent, ["hello", "world"], output)

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
    agent = make_agent(ChunkedFakeLLMClient())
    output = io.StringIO()

    run(agent, ["hi"], output)

    assert output.getvalue() == WELCOME_MESSAGE + PROMPT + "Hello\n" + PROMPT + GOODBYE_MESSAGE


def test_run_stops_on_exit_command():
    agent = make_agent(FakeLLMClient())
    output = io.StringIO()

    run(agent, ["hello", "exit", "should not be sent"], output)

    assert output.getvalue() == (
        WELCOME_MESSAGE + PROMPT + "echo: hello\n" + PROMPT + GOODBYE_MESSAGE
    )


def test_run_skips_blank_lines():
    agent = make_agent(FakeLLMClient())
    output = io.StringIO()

    run(agent, ["", "   ", "hi"], output)

    assert output.getvalue() == (
        WELCOME_MESSAGE + PROMPT + PROMPT + PROMPT + "echo: hi\n" + PROMPT + GOODBYE_MESSAGE
    )


def test_run_prints_a_prompt_before_reading_each_line():
    agent = make_agent(FakeLLMClient())
    output = io.StringIO()

    run(agent, ["hello"], output)

    assert PROMPT in output.getvalue()


def test_run_sends_every_line_in_the_same_session():
    agent = ScriptedAgent([])

    run(agent, ["hello", "world"], io.StringIO())

    assert [r.message for r in agent.requests] == [
        Message.from_text("user", "hello"),
        Message.from_text("user", "world"),
    ]
    assert agent.requests[0].session_id == agent.requests[1].session_id


def test_run_announces_tool_use():
    agent = ScriptedAgent([ToolStarted(name="lookup", arguments={"q": "x"})])
    output = io.StringIO()

    run(agent, ["hi"], output)

    assert "[使用工具: lookup arguments={'q': 'x'}]" in output.getvalue()


def test_run_reports_when_the_tool_limit_is_reached():
    agent = ScriptedAgent([ToolLimitReached()])
    output = io.StringIO()

    run(agent, ["hi"], output)

    assert TOOL_LIMIT_NOTICE in output.getvalue()


def test_run_reports_llm_errors_and_keeps_the_session_alive():
    agent = make_agent(FailsOnceFakeLLMClient())
    output = io.StringIO()

    run(agent, ["hello", "again"], output)

    assert output.getvalue() == (
        WELCOME_MESSAGE
        + PROMPT
        + f"{ERROR_PREFIX}connection lost\n"
        + PROMPT
        + "recovered\n"
        + PROMPT
        + GOODBYE_MESSAGE
    )


class RecordingWriter:
    def __init__(self, output: io.StringIO) -> None:
        self._output = output
        self.log: list[str] = []

    def write(self, text: str) -> None:
        self.log.append(f"write:{text}")

    def flush(self) -> None:
        self.log.append(f"flush@{len(self._output.getvalue())}")


def test_run_leaves_the_prompt_to_the_input_source_when_told_to():
    output = io.StringIO()

    run(make_agent(FakeLLMClient()), ["hi"], output, prompt="")

    assert output.getvalue() == WELCOME_MESSAGE + "echo: hi\n" + GOODBYE_MESSAGE


def test_run_sends_text_to_the_given_writer_and_flushes_at_the_end_of_the_reply():
    output = io.StringIO()
    writer = RecordingWriter(output)

    run(ScriptedAgent([TextDelta("Hel"), TextDelta("lo")]), ["hi"], output, text_writer=writer)

    assert [entry for entry in writer.log if entry.startswith("write:")] == [
        "write:Hel",
        "write:lo",
    ]
    assert writer.log[-1].startswith("flush")
    assert "Hello" not in output.getvalue()


def test_run_flushes_buffered_text_before_announcing_a_tool():
    output = io.StringIO()
    writer = RecordingWriter(output)
    agent = ScriptedAgent([TextDelta("text"), ToolStarted(name="lookup", arguments={})])

    run(agent, ["hi"], output, text_writer=writer)

    flush_position = int(writer.log[1].removeprefix("flush@"))
    assert flush_position < output.getvalue().index("[使用工具")


def test_run_flushes_buffered_text_before_reporting_an_error():
    class FailingAgent:
        name = "failing"

        def run(self, request: AgentRequest) -> Iterator[Event]:
            yield TextDelta("partial")
            raise RuntimeError("connection lost")

    output = io.StringIO()
    writer = RecordingWriter(output)

    run(FailingAgent(), ["hi"], output, text_writer=writer)

    flush_position = int(writer.log[1].removeprefix("flush@"))
    assert flush_position <= output.getvalue().index(ERROR_PREFIX)


def _markdown_writer() -> tuple[MarkdownBlockWriter, io.StringIO]:
    output = io.StringIO()
    return MarkdownBlockWriter(Console(file=output, width=80)), output


def test_markdown_writer_holds_an_unfinished_block():
    writer, output = _markdown_writer()

    writer.write("first para")
    writer.write("graph")

    assert output.getvalue() == ""


def test_markdown_writer_renders_a_block_when_a_blank_line_arrives():
    writer, output = _markdown_writer()

    writer.write("## Title\n")
    writer.write("\nnext block")

    assert "Title" in output.getvalue()
    assert "##" not in output.getvalue()
    assert "next block" not in output.getvalue()


def test_markdown_writer_flush_renders_the_remaining_text():
    writer, output = _markdown_writer()

    writer.write("last block")
    writer.flush()
    writer.flush()

    assert output.getvalue().count("last block") == 1


def test_markdown_writer_renders_a_table_with_cjk_text():
    writer, output = _markdown_writer()

    writer.write("| 議題 | 查證 |\n| --- | --- |\n| 美國期中選舉 | 僅標題 |\n\n")

    rendered = output.getvalue()
    assert "美國期中選舉" in rendered
    assert "| ---" not in rendered


def test_markdown_writer_keeps_a_code_block_with_blank_lines_together():
    writer, output = _markdown_writer()

    writer.write("```\na\n\nb\n")

    assert output.getvalue() == ""


def test_prompt_lines_reads_with_the_prompt_until_end_of_input():
    prompts: list[str] = []
    lines = iter(["hello", "world"])

    def read_line(prompt: str) -> str:
        prompts.append(prompt)
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None

    assert list(prompt_lines(read_line)) == ["hello", "world"]
    assert prompts == [PROMPT, PROMPT, PROMPT]


def test_prompt_lines_stops_on_ctrl_c():
    def read_line(prompt: str) -> str:
        raise KeyboardInterrupt

    assert list(prompt_lines(read_line)) == []
