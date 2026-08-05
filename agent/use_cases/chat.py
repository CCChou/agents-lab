from collections.abc import Iterator

from agent.domain.interfaces import LLMClient
from agent.domain.message import Message


class Chat:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client
        self._history: list[Message] = []

    def send(self, message: str) -> Iterator[str]:
        self._history.append(Message(role="user", content=message))
        reply_chunks: list[str] = []
        for chunk in self._llm_client.stream(list(self._history)):
            reply_chunks.append(chunk)
            yield chunk
        self._history.append(Message(role="assistant", content="".join(reply_chunks)))
