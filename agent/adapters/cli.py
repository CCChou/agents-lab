from collections.abc import Callable, Iterable, Iterator
from typing import Protocol, TextIO

from rich.console import Console
from rich.markdown import Markdown

from agent.domain.event import Event, TextDelta, ToolLimitReached, ToolStarted
from agent.domain.interfaces import Agent, SessionLifecycle
from agent.domain.message import Message
from agent.domain.request import AgentRequest

EXIT_COMMANDS = {"exit", "quit"}
RESET_COMMANDS = {"/reset"}
WELCOME_MESSAGE = (
    "Welcome! Type a message and press Enter to chat. Type 'exit' or 'quit' to leave.\n"
    "Type '/reset' to start a new conversation.\n"
)
RESET_MESSAGE = "[已開始新對話]\n"
GOODBYE_MESSAGE = "Goodbye!\n"
ERROR_PREFIX = "Error: "
TOOL_LIMIT_NOTICE = "\n[已達到工具呼叫上限，停止重試]\n"
PROMPT = "> "
OWNER_ID = "cli"


class TextWriter(Protocol):
    def write(self, text: str) -> None: ...

    def flush(self) -> None: ...


class PlainTextWriter:
    def __init__(self, output: TextIO) -> None:
        self._output = output

    def write(self, text: str) -> None:
        self._output.write(text)

    def flush(self) -> None:
        pass


class MarkdownBlockWriter:
    def __init__(self, console: Console) -> None:
        self._console = console
        self._buffer = ""

    def write(self, text: str) -> None:
        self._buffer += text
        finished, separator, rest = self._buffer.rpartition("\n\n")
        if separator and finished.count("```") % 2 == 0:
            self._buffer = rest
            self._render(finished)

    def flush(self) -> None:
        text, self._buffer = self._buffer, ""
        self._render(text)

    def _render(self, text: str) -> None:
        if text.strip():
            self._console.print(Markdown(text))
            self._console.print()


def prompt_lines(read_line: Callable[[str], str]) -> Iterator[str]:
    while True:
        try:
            yield read_line(PROMPT)
        except (EOFError, KeyboardInterrupt):
            return


def _write_event(event: Event, writer: TextWriter, output: TextIO) -> None:
    match event:
        case TextDelta(text):
            writer.write(text)
        case ToolStarted(name, arguments):
            writer.flush()
            output.write(f"\n[使用工具: {name} arguments={arguments}]\n")
        case ToolLimitReached():
            writer.flush()
            output.write(TOOL_LIMIT_NOTICE)


def run(
    agent: Agent,
    sessions: SessionLifecycle,
    input_lines: Iterable[str],
    output: TextIO,
    *,
    prompt: str = PROMPT,
    text_writer: TextWriter | None = None,
) -> None:
    writer = text_writer or PlainTextWriter(output)
    output.write(WELCOME_MESSAGE)
    lines = iter(input_lines)
    while True:
        output.write(prompt)
        output.flush()
        try:
            line = next(lines)
        except StopIteration:
            break
        message = line.strip()
        if not message:
            continue
        if message in EXIT_COMMANDS:
            break
        if message in RESET_COMMANDS:
            try:
                sessions.start_new(OWNER_ID)
            except Exception as exc:  # noqa: BLE001 - a remote session service may be unreachable
                output.write(f"{ERROR_PREFIX}{exc}\n")
            else:
                output.write(RESET_MESSAGE)
            continue
        try:
            session_id = sessions.current_or_start(OWNER_ID)
            request = AgentRequest(session_id, Message.from_text("user", message))
            for event in agent.run(request):
                _write_event(event, writer, output)
                output.flush()
            writer.flush()
        except Exception as exc:  # noqa: BLE001 - an LLM failure should not end the session
            writer.flush()
            output.write(f"{ERROR_PREFIX}{exc}")
        output.write("\n")
    output.write(GOODBYE_MESSAGE)
