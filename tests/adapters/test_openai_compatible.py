import json

import httpx

from agent.adapters.openai_compatible import OpenAICompatibleLLMClient
from agent.domain.interfaces import LLMClient


def test_satisfies_llm_client_port():
    client = OpenAICompatibleLLMClient(base_url="https://example.test/v1", api_key="key", model="m")

    assert isinstance(client, LLMClient)


def test_stream_sends_expected_request_and_yields_content_chunks():
    captured: dict[str, httpx.Request] = {}
    sse_body = (
        b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":" world"}}]}\n\n'
        b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, content=sse_body)

    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="secret-key",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )

    chunks = list(client.stream("ping"))

    request = captured["request"]
    assert request.method == "POST"
    assert request.url == "https://example.test/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer secret-key"
    assert json.loads(request.content) == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "ping"}],
        "stream": True,
    }
    assert chunks == ["Hello", " world"]
