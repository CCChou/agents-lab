from collections.abc import Iterator

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI

from agent.domain.message import Message, Role

_ROLE_TO_LANGCHAIN_MESSAGE: dict[Role, type[BaseMessage]] = {
    "user": HumanMessage,
    "assistant": AIMessage,
}


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        chat_model: BaseChatModel | None = None,
    ) -> None:
        self._chat_model = chat_model or ChatOpenAI(
            base_url=base_url,
            api_key=api_key,
            model=model,
        )

    def stream(self, messages: list[Message]) -> Iterator[str]:
        langchain_messages = [
            _ROLE_TO_LANGCHAIN_MESSAGE[message.role](content=message.content)
            for message in messages
        ]
        for chunk in self._chat_model.stream(langchain_messages):
            if chunk.content:
                yield chunk.content
