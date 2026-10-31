from collections.abc import Iterable
from typing import TextIO

from agent.domain.event import Event, TextDelta, ToolLimitReached, ToolStarted
from agent.use_cases.chat import Chat

EXIT_COMMANDS = {"exit", "quit"}
WELCOME_MESSAGE = (
    "Welcome! Type a message and press Enter to chat. Type 'exit' or 'quit' to leave.\n"
)
GOODBYE_MESSAGE = "Goodbye!\n"
ERROR_PREFIX = "Error: "
TOOL_LIMIT_NOTICE = "\n[已達到工具呼叫上限，停止重試]\n"
PROMPT = "> "


def _write_event(event: Event, output: TextIO) -> None:
    match event:
        case TextDelta(text):
            output.write(text)
        case ToolStarted(name, arguments):
            output.write(f"\n[使用工具: {name} arguments={arguments}]\n")
        case ToolLimitReached():
            output.write(TOOL_LIMIT_NOTICE)


def run(chat: Chat, input_lines: Iterable[str], output: TextIO) -> None:
    output.write(WELCOME_MESSAGE)
    lines = iter(input_lines)
    while True:
        output.write(PROMPT)
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
        try:
            for event in chat.send(message):
                _write_event(event, output)
                output.flush()
        except Exception as exc:  # noqa: BLE001 - an LLM failure should not end the session
            output.write(f"{ERROR_PREFIX}{exc}")
        output.write("\n")
    output.write(GOODBYE_MESSAGE)
