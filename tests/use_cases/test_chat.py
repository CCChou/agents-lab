from collections.abc import Iterator

from agent.domain.interfaces import LLMClient
from agent.domain.message import Message
from agent.use_cases.chat import Chat


class FakeLLMClient:
    def __init__(self, replies: list[list[str]]) -> None:
        self._replies = iter(replies)
        self.received_messages_per_call: list[list[Message]] = []

    def stream(self, messages: list[Message]) -> Iterator[str]:
        self.received_messages_per_call.append(messages)
        yield from next(self._replies)


def test_fake_satisfies_llm_client_port():
    assert isinstance(FakeLLMClient(replies=[]), LLMClient)


def test_send_forwards_the_message_and_yields_the_llm_reply_chunks():
    llm_client = FakeLLMClient(replies=[["hello ", "there"]])
    chat = Chat(llm_client)

    reply_chunks = list(chat.send("hi"))

    assert reply_chunks == ["hello ", "there"]
    assert llm_client.received_messages_per_call == [[Message(role="user", content="hi")]]


def test_send_includes_prior_turns_in_the_next_request():
    llm_client = FakeLLMClient(replies=[["hi there"], ["I'm good, thanks"]])
    chat = Chat(llm_client)

    list(chat.send("hello"))
    list(chat.send("how are you"))

    assert llm_client.received_messages_per_call[1] == [
        Message(role="user", content="hello"),
        Message(role="assistant", content="hi there"),
        Message(role="user", content="how are you"),
    ]
