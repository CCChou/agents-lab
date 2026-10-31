from collections.abc import Iterator

from agent.domain.interfaces import LLMClient
from agent.domain.message import Message
from agent.domain.tool import Tool, ToolCall

TOOL_LIMIT_RESULT = "未執行：已達到工具呼叫上限。請根據目前資訊回答，並說明缺少哪些內容。"
TOOL_LIMIT_NOTICE = "\n[已達到工具呼叫上限，停止重試]\n"


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
            self._history.append(Message(role="system", content=system_prompt))

    def send(self, message: str) -> Iterator[str]:
        self._history.append(Message(role="user", content=message))
        iterations = 0
        tools = list(self._tools.values()) or None
        while True:
            iterations += 1
            reply_text, tool_calls = self._ask_llm(tools)
            if reply_text:
                yield reply_text

            if not tool_calls:
                return

            if iterations >= self._max_tool_iterations:
                yield self._finish_at_tool_limit(tool_calls)
                return

            for call in tool_calls:
                notice = f"\n[使用工具: {call.name} arguments={call.arguments}]\n"
                yield notice
                self._history.append(
                    Message(role="tool", content=self._run_tool(call), tool_call_id=call.id)
                )

    def _ask_llm(self, tools: list[Tool] | None) -> tuple[str, list[ToolCall]]:
        text_chunks: list[str] = []
        tool_calls: list[ToolCall] = []
        for event in self._llm_client.stream(list(self._history), tools):
            if isinstance(event, ToolCall):
                tool_calls.append(event)
            else:
                text_chunks.append(event)

        reply_text = "".join(text_chunks)
        self._history.append(
            Message(role="assistant", content=reply_text, tool_calls=tool_calls or None)
        )
        return reply_text, tool_calls

    def _finish_at_tool_limit(self, tool_calls: list[ToolCall]) -> str:
        self._decline_tool_calls(tool_calls)
        try:
            reply_text, unexpected_calls = self._ask_llm(None)
        except Exception:  # noqa: BLE001 - some APIs reject tool history without tool definitions
            return TOOL_LIMIT_NOTICE
        self._decline_tool_calls(unexpected_calls)
        return reply_text or TOOL_LIMIT_NOTICE

    def _decline_tool_calls(self, tool_calls: list[ToolCall]) -> None:
        for call in tool_calls:
            self._history.append(
                Message(role="tool", content=TOOL_LIMIT_RESULT, tool_call_id=call.id)
            )

    def _run_tool(self, call: ToolCall) -> str:
        tool = self._tools.get(call.name)
        if tool is None:
            return f"Error: unknown tool '{call.name}'"
        try:
            return tool.run(call.arguments)
        except Exception as exc:  # noqa: BLE001 - surfaced to the LLM instead of crashing the chat
            return f"Error calling tool '{call.name}': {exc}"
