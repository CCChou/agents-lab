import json
from functools import partial

import httpx
import pytest
from langchain_openai import ChatOpenAI

from agent.adapters import openai_compatible
from agent.adapters.openai_compatible import OpenAICompatibleLLMClient
from agent.domain.interfaces import LLMClient
from agent.domain.message import Message
from agent.domain.tool import ToolCall


class FakeChunk:
    def __init__(self, content: str = "", tool_calls: list[dict] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls or []

    def __add__(self, other: "FakeChunk") -> "FakeChunk":
        return FakeChunk(
            content=self.content + other.content,
            tool_calls=other.tool_calls or self.tool_calls,
        )


class FakeChatModel:
    def __init__(self, chunks: list[FakeChunk]) -> None:
        self._chunks = chunks
        self.received_messages = None
        self.bound_tools = None

    def bind_tools(self, tools: list[dict]) -> "FakeChatModel":
        self.bound_tools = tools
        return self

    def stream(self, messages):
        self.received_messages = messages
        yield from self._chunks


class FakeTool:
    def __init__(self) -> None:
        self.name = "lookup"
        self.description = "looks things up"
        self.parameters_schema = {"type": "object", "properties": {"q": {"type": "string"}}}

    def run(self, arguments: dict) -> str:
        return "unused"


def test_satisfies_llm_client_port():
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="m",
        chat_model=FakeChatModel(chunks=[]),
    )

    assert isinstance(client, LLMClient)


def test_stream_converts_messages_to_langchain_messages_and_yields_content_chunks():
    fake_chat_model = FakeChatModel(chunks=[FakeChunk("Hello"), FakeChunk(" world")])
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="test-model",
        chat_model=fake_chat_model,
    )

    chunks = list(
        client.stream(
            [
                Message.from_text("user", "hi"),
                Message.from_text("assistant", "hello"),
                Message.from_text("user", "ping"),
            ]
        )
    )

    assert chunks == ["Hello", " world"]
    sent = fake_chat_model.received_messages
    assert [type(m).__name__ for m in sent] == ["HumanMessage", "AIMessage", "HumanMessage"]
    assert [m.content for m in sent] == ["hi", "hello", "ping"]


def test_stream_skips_empty_chunks():
    fake_chat_model = FakeChatModel(chunks=[FakeChunk("Hello"), FakeChunk(""), FakeChunk(" world")])
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="test-model",
        chat_model=fake_chat_model,
    )

    chunks = list(client.stream([Message.from_text("user", "ping")]))

    assert chunks == ["Hello", " world"]


def test_stream_converts_system_role_to_system_message():
    fake_chat_model = FakeChatModel(chunks=[FakeChunk("ok")])
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="test-model",
        chat_model=fake_chat_model,
    )

    list(
        client.stream(
            [
                Message.from_text("system", "be terse"),
                Message.from_text("user", "hi"),
            ]
        )
    )

    sent = fake_chat_model.received_messages
    assert [type(m).__name__ for m in sent] == ["SystemMessage", "HumanMessage"]
    assert [m.content for m in sent] == ["be terse", "hi"]


def test_stream_converts_tool_role_to_tool_message_with_call_id():
    fake_chat_model = FakeChatModel(chunks=[FakeChunk("ok")])
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="test-model",
        chat_model=fake_chat_model,
    )

    list(client.stream([Message.from_text("tool", "72F", tool_call_id="call_1")]))

    sent = fake_chat_model.received_messages
    assert type(sent[0]).__name__ == "ToolMessage"
    assert sent[0].tool_call_id == "call_1"
    assert sent[0].content == "72F"


def test_stream_converts_assistant_tool_calls_to_ai_message_tool_calls():
    fake_chat_model = FakeChatModel(chunks=[FakeChunk("ok")])
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="test-model",
        chat_model=fake_chat_model,
    )

    list(
        client.stream(
            [
                Message.from_text(
                    "assistant",
                    "",
                    tool_calls=[ToolCall(id="call_1", name="lookup", arguments={"q": "x"})],
                )
            ]
        )
    )

    sent = fake_chat_model.received_messages
    assert sent[0].tool_calls == [
        {"id": "call_1", "name": "lookup", "args": {"q": "x"}, "type": "tool_call"}
    ]


def test_stream_binds_tools_to_the_chat_model_in_openai_function_format():
    fake_chat_model = FakeChatModel(chunks=[FakeChunk("ok")])
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="test-model",
        chat_model=fake_chat_model,
    )

    list(client.stream([Message.from_text("user", "hi")], tools=[FakeTool()]))

    assert fake_chat_model.bound_tools == [
        {
            "type": "function",
            "function": {
                "name": "lookup",
                "description": "looks things up",
                "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
            },
        }
    ]


def test_stream_yields_tool_calls_after_the_final_accumulated_chunk():
    fake_chat_model = FakeChatModel(
        chunks=[
            FakeChunk(""),
            FakeChunk("", tool_calls=[{"id": "call_1", "name": "lookup", "args": {"q": "x"}}]),
        ]
    )
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="test-model",
        chat_model=fake_chat_model,
    )

    events = list(client.stream([Message.from_text("user", "hi")], tools=[FakeTool()]))

    assert events == [ToolCall(id="call_1", name="lookup", arguments={"q": "x"})]


class FlakyChatModel(FakeChatModel):
    def __init__(self, attempts: list[list[FakeChunk | Exception]]) -> None:
        super().__init__(chunks=[])
        self._attempts = iter(attempts)
        self.attempt_count = 0

    def stream(self, messages):
        self.attempt_count += 1
        for item in next(self._attempts):
            if isinstance(item, Exception):
                raise item
            yield item


def _flaky_client(attempts: list[list[FakeChunk | Exception]]):
    chat_model = FlakyChatModel(attempts)
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1", api_key="key", model="m", chat_model=chat_model
    )
    return client, chat_model


INVALID_TOOL_CALL = RuntimeError(
    "Error code: 400 - tool call validation failed: attempted to call tool 'lookpu'"
)


def test_stream_retries_once_when_the_service_rejects_an_invalid_tool_call():
    client, chat_model = _flaky_client([[INVALID_TOOL_CALL], [FakeChunk("recovered")]])

    assert list(client.stream([Message.from_text("user", "hi")])) == ["recovered"]
    assert chat_model.attempt_count == 2


def test_stream_gives_up_when_the_retry_is_also_rejected():
    client, chat_model = _flaky_client([[INVALID_TOOL_CALL], [INVALID_TOOL_CALL]])

    with pytest.raises(RuntimeError, match="tool call validation failed"):
        list(client.stream([Message.from_text("user", "hi")]))
    assert chat_model.attempt_count == 2


def test_stream_does_not_retry_other_errors():
    client, chat_model = _flaky_client([[RuntimeError("connection lost")]])

    with pytest.raises(RuntimeError, match="connection lost"):
        list(client.stream([Message.from_text("user", "hi")]))
    assert chat_model.attempt_count == 1


def test_stream_does_not_retry_after_text_was_already_sent():
    client, chat_model = _flaky_client([[FakeChunk("partial"), INVALID_TOOL_CALL]])

    stream = client.stream([Message.from_text("user", "hi")])

    assert next(stream) == "partial"
    with pytest.raises(RuntimeError, match="tool call validation failed"):
        next(stream)
    assert chat_model.attempt_count == 1


def _capture_requests(monkeypatch) -> list[httpx.Request]:
    requests: list[httpx.Request] = []
    chunk = {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "test-model",
        "choices": [{"index": 0, "delta": {"content": "ok"}, "finish_reason": "stop"}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n",
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        openai_compatible, "ChatOpenAI", partial(ChatOpenAI, http_client=http_client)
    )
    return requests


def test_stream_sends_configured_reasoning_effort_to_chat_completions(monkeypatch):
    requests = _capture_requests(monkeypatch)
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="gpt-6-luna",
        reasoning_effort="none",
    )

    list(client.stream([Message.from_text("user", "hi")], tools=[FakeTool()]))

    assert requests[0].url.path == "/v1/chat/completions"
    assert json.loads(requests[0].content)["reasoning_effort"] == "none"


def test_stream_omits_reasoning_effort_when_not_configured(monkeypatch):
    requests = _capture_requests(monkeypatch)
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="test-model",
    )

    list(client.stream([Message.from_text("user", "hi")]))

    assert "reasoning_effort" not in json.loads(requests[0].content)


def test_stream_sends_the_configured_temperature(monkeypatch):
    requests = _capture_requests(monkeypatch)
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="test-model",
        temperature=0.0,
    )

    list(client.stream([Message.from_text("user", "hi")]))

    assert json.loads(requests[0].content)["temperature"] == 0.0


def test_stream_omits_temperature_when_not_configured(monkeypatch):
    requests = _capture_requests(monkeypatch)
    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="test-model",
    )

    list(client.stream([Message.from_text("user", "hi")]))

    assert "temperature" not in json.loads(requests[0].content)
