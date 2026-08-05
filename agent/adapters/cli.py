from collections.abc import Iterable
from typing import TextIO

from agent.use_cases.chat import Chat

EXIT_COMMANDS = {"exit", "quit"}
WELCOME_MESSAGE = (
    "Welcome! Type a message and press Enter to chat. Type 'exit' or 'quit' to leave.\n"
)
GOODBYE_MESSAGE = "Goodbye!\n"


def run(chat: Chat, input_lines: Iterable[str], output: TextIO) -> None:
    output.write(WELCOME_MESSAGE)
    for line in input_lines:
        message = line.strip()
        if not message:
            continue
        if message in EXIT_COMMANDS:
            break
        for chunk in chat.send(message):
            output.write(chunk)
            output.flush()
        output.write("\n")
    output.write(GOODBYE_MESSAGE)
