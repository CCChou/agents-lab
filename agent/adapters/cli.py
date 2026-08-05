from collections.abc import Iterable
from typing import TextIO

from agent.use_cases.chat import Chat

EXIT_COMMANDS = {"exit", "quit"}


def run(chat: Chat, input_lines: Iterable[str], output: TextIO) -> None:
    for line in input_lines:
        message = line.strip()
        if not message:
            continue
        if message in EXIT_COMMANDS:
            break
        reply = chat.send(message)
        output.write(f"{reply}\n")
