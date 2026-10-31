from collections.abc import Generator, Iterator

from agent.domain.event import Event, TextDelta, ToolLimitReached, ToolStarted
from agent.domain.interfaces import LLMClient
from agent.domain.message import Message
from agent.domain.tool import Tool, ToolCall

TOOL_LIMIT_RESULT = "未執行：已達到工具呼叫上限。請根據目前資訊回答，並說明缺少哪些內容。"


class Chat:
    def __init__(
        self,
        llm_client: LLMClient,
        system_prompt: str | None = None,
        tools: list[Tool] | None = None,
        max_tool_iterations: int = 5,
    ) -> None:
        self._llm_client = llm_client
        self._tools = {tool.name: tool for tool in tools or []}
        self._history: list[Message] = []
        self._max_tool_iterations = max_tool_iterations
        if system_prompt:
            self._history.append(Message.from_text("system", system_prompt))

    def send(self, message: str) -> Iterator[Event]:
        self._history.append(Message.from_text("user", message))
        iterations = 0
        tools = list(self._tools.values()) or None
        while True:
            iterations += 1
            _, tool_calls = yield from self._ask_llm(tools)

            if not tool_calls:
                return

            if iterations >= self._max_tool_iterations:
                yield from self._finish_at_tool_limit(tool_calls)
                return

            for call in tool_calls:
                yield ToolStarted(name=call.name, arguments=call.arguments)
                self._history.append(
                    Message.from_text("tool", self._run_tool(call), tool_call_id=call.id)
                )

    def _ask_llm(
        self, tools: list[Tool] | None
    ) -> Generator[TextDelta, None, tuple[str, list[ToolCall]]]:
        text_chunks: list[str] = []
        tool_calls: list[ToolCall] = []
        for event in self._llm_client.stream(list(self._history), tools):
            if isinstance(event, ToolCall):
                tool_calls.append(event)
            else:
                text_chunks.append(event)
                yield TextDelta(event)

        reply_text = "".join(text_chunks)
        self._history.append(
            Message.from_text("assistant", reply_text, tool_calls=tool_calls or None)
        )
        return reply_text, tool_calls

    def _finish_at_tool_limit(self, tool_calls: list[ToolCall]) -> Iterator[Event]:
        self._decline_tool_calls(tool_calls)
        try:
            reply_text, unexpected_calls = yield from self._ask_llm(None)
        except Exception:  # noqa: BLE001 - some APIs reject tool history without tool definitions
            yield ToolLimitReached()
            return
        self._decline_tool_calls(unexpected_calls)
        if not reply_text:
            yield ToolLimitReached()

    def _decline_tool_calls(self, tool_calls: list[ToolCall]) -> None:
        for call in tool_calls:
            self._history.append(Message.from_text("tool", TOOL_LIMIT_RESULT, tool_call_id=call.id))

    def _run_tool(self, call: ToolCall) -> str:
        tool = self._tools.get(call.name)
        if tool is None:
            return f"Error: unknown tool '{call.name}'"
        try:
            return tool.run(call.arguments)
        except Exception as exc:  # noqa: BLE001 - surfaced to the LLM instead of crashing the chat
            return f"Error calling tool '{call.name}': {exc}"
