from collections.abc import Iterator

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI


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

    def stream(self, prompt: str) -> Iterator[str]:
        for chunk in self._chat_model.stream([HumanMessage(content=prompt)]):
            if chunk.content:
                yield chunk.content
