from collections.abc import Iterator

from agent.domain.interfaces import LLMClient
from agent.use_cases.chat import Chat


class FakeLLMClient:
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks
        self.received_prompt: str | None = None

    def stream(self, prompt: str) -> Iterator[str]:
        self.received_prompt = prompt
        yield from self._chunks


def test_fake_satisfies_llm_client_port():
    assert isinstance(FakeLLMClient(chunks=[]), LLMClient)


def test_send_forwards_the_message_and_yields_the_llm_reply_chunks():
    llm_client = FakeLLMClient(chunks=["hello ", "there"])
    chat = Chat(llm_client)

    reply_chunks = list(chat.send("hi"))

    assert reply_chunks == ["hello ", "there"]
    assert llm_client.received_prompt == "hi"
