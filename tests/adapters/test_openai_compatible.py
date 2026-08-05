import json

import httpx

from agent.adapters.openai_compatible import OpenAICompatibleLLMClient
from agent.domain.interfaces import LLMClient


def test_satisfies_llm_client_port():
    client = OpenAICompatibleLLMClient(base_url="https://example.test/v1", api_key="key", model="m")

    assert isinstance(client, LLMClient)


def test_complete_sends_expected_request_and_parses_response():
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"choices": [{"message": {"content": "pong"}}]})

    client = OpenAICompatibleLLMClient(
        base_url="https://example.test/v1",
        api_key="secret-key",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )

    result = client.complete("ping")

    request = captured["request"]
    assert request.method == "POST"
    assert request.url == "https://example.test/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer secret-key"
    assert json.loads(request.content) == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "ping"}],
    }
    assert result == "pong"
