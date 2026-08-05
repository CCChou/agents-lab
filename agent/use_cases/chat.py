from collections.abc import Iterator

from agent.domain.interfaces import LLMClient


class Chat:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def send(self, message: str) -> Iterator[str]:
        return self._llm_client.stream(message)
