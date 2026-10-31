from collections.abc import Iterator

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from agent.domain.message import Message
from agent.domain.tool import Tool, ToolCall


def _to_openai_tool_spec(tool: Tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters_schema,
        },
    }


def _to_langchain_message(message: Message) -> BaseMessage:
    if message.role == "user":
        return HumanMessage(content=message.content)
    if message.role == "system":
        return SystemMessage(content=message.content)
    if message.role == "tool":
        return ToolMessage(content=message.content, tool_call_id=message.tool_call_id)
    return AIMessage(
        content=message.content,
        tool_calls=[
            {"id": call.id, "name": call.name, "args": call.arguments}
            for call in (message.tool_calls or [])
        ],
    )


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

    def stream(
        self, messages: list[Message], tools: list[Tool] | None = None
    ) -> Iterator[str | ToolCall]:
        langchain_messages = [_to_langchain_message(message) for message in messages]

        chat_model = self._chat_model
        if tools:
            chat_model = chat_model.bind_tools([_to_openai_tool_spec(tool) for tool in tools])

        accumulated = None
        for chunk in chat_model.stream(langchain_messages):
            if chunk.content:
                yield chunk.content
            accumulated = chunk if accumulated is None else accumulated + chunk

        if accumulated is not None:
            for tool_call in accumulated.tool_calls:
                yield ToolCall(
                    id=tool_call["id"], name=tool_call["name"], arguments=tool_call["args"]
                )
