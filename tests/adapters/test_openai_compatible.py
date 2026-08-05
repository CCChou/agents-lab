from types import SimpleNamespace

from agent.adapters.openai_compatible import OpenAICompatibleLLMClient
from agent.domain.interfaces import LLMClient
from agent.domain.message import Message


class FakeChatModel:
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks
        self.received_messages = None

    def stream(self, messages):
        self.received_messages = messages
        for text in self._chunks:
            yield SimpleNamespace(content=text)


def test_satisfies_llm_client_port():
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="m",
        chat_model=FakeChatModel(chunks=[]),
    )

    assert isinstance(client, LLMClient)


def test_stream_converts_messages_to_langchain_messages_and_yields_content_chunks():
    fake_chat_model = FakeChatModel(chunks=["Hello", " world"])
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="test-model",
        chat_model=fake_chat_model,
    )

    chunks = list(
        client.stream(
            [
                Message(role="user", content="hi"),
                Message(role="assistant", content="hello"),
                Message(role="user", content="ping"),
            ]
        )
    )

    assert chunks == ["Hello", " world"]
    sent = fake_chat_model.received_messages
    assert [type(m).__name__ for m in sent] == ["HumanMessage", "AIMessage", "HumanMessage"]
    assert [m.content for m in sent] == ["hi", "hello", "ping"]


def test_stream_skips_empty_chunks():
    fake_chat_model = FakeChatModel(chunks=["Hello", "", " world"])
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="test-model",
        chat_model=fake_chat_model,
    )

    chunks = list(client.stream([Message(role="user", content="ping")]))

    assert chunks == ["Hello", " world"]
