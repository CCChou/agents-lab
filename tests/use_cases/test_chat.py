from agent.domain.interfaces import LLMClient
from agent.use_cases.chat import Chat


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self._response = response
        self.received_prompt: str | None = None

    def complete(self, prompt: str) -> str:
        self.received_prompt = prompt
        return self._response


def test_fake_satisfies_llm_client_port():
    assert isinstance(FakeLLMClient(response=""), LLMClient)


def test_send_forwards_the_message_and_returns_the_llm_reply():
    llm_client = FakeLLMClient(response="hello there")
    chat = Chat(llm_client)

    reply = chat.send("hi")

    assert reply == "hello there"
    assert llm_client.received_prompt == "hi"
