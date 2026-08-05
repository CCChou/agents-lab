from agent.domain.interfaces import LLMClient


class Chat:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def send(self, message: str) -> str:
        return self._llm_client.complete(message)
