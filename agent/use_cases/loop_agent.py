from collections import Counter
from collections.abc import Generator, Iterator

from agent.domain.agent_spec import AgentSpec
from agent.domain.event import Event, TextDelta, ToolLimitReached, ToolStarted
from agent.domain.interfaces import ConversationStore, LLMClient
from agent.domain.message import Message
from agent.domain.request import AgentRequest
from agent.domain.tool import Tool, ToolCall
from agent.use_cases.context_builder import ContextBuilder
from agent.use_cases.tool_registry import ToolRegistry

TOOL_LIMIT_RESULT = "未執行：已達到工具呼叫上限。請根據目前資訊回答，並說明缺少哪些內容。"
TOOL_CALL_LIMIT_RESULT = (
    "未執行：{name} 這一輪已達到 {limit} 次上限。不要再呼叫這個工具，請根據目前資訊回答。"
)


class LoopAgent:
    def __init__(
        self,
        spec: AgentSpec,
        llm_client: LLMClient,
        store: ConversationStore,
        context_builder: ContextBuilder,
        tool_registry: ToolRegistry,
    ) -> None:
        self.name = spec.name
        self._spec = spec
        self._llm_client = llm_client
        self._store = store
        self._context_builder = context_builder
        self._tools = {tool.name: tool for tool in tool_registry.get(spec.tools)}

    def run(self, request: AgentRequest) -> Iterator[Event]:
        context = self._context_builder.build(self._spec, request.session_id)
        messages = [*context, request.message]
        yield from self._run_turn(messages)
        self._store.append(request.session_id, messages[len(context) :])

    def _run_turn(self, messages: list[Message]) -> Iterator[Event]:
        iterations = 0
        tools = list(self._tools.values()) or None
        call_counts: Counter[str] = Counter()
        while True:
            iterations += 1
            _, tool_calls = yield from self._ask_llm(messages, tools)

            if not tool_calls:
                return

            if iterations >= self._spec.max_tool_iterations:
                yield from self._finish_at_tool_limit(messages, tool_calls)
                return

            for call in tool_calls:
                limit = self._spec.tool_call_limits.get(call.name)
                if limit is not None and call_counts[call.name] >= limit:
                    result = TOOL_CALL_LIMIT_RESULT.format(name=call.name, limit=limit)
                    messages.append(Message.from_text("tool", result, tool_call_id=call.id))
                    continue
                call_counts[call.name] += 1
                yield ToolStarted(name=call.name, arguments=call.arguments)
                messages.append(
                    Message.from_text("tool", self._run_tool(call), tool_call_id=call.id)
                )

    def _ask_llm(
        self, messages: list[Message], tools: list[Tool] | None
    ) -> Generator[TextDelta, None, tuple[str, list[ToolCall]]]:
        text_chunks: list[str] = []
        tool_calls: list[ToolCall] = []
        for event in self._llm_client.stream(list(messages), tools):
            if isinstance(event, ToolCall):
                tool_calls.append(event)
            else:
                text_chunks.append(event)
                yield TextDelta(event)

        reply_text = "".join(text_chunks)
        messages.append(Message.from_text("assistant", reply_text, tool_calls=tool_calls or None))
        return reply_text, tool_calls

    def _finish_at_tool_limit(
        self, messages: list[Message], tool_calls: list[ToolCall]
    ) -> Iterator[Event]:
        self._decline_tool_calls(messages, tool_calls)
        try:
            reply_text, unexpected_calls = yield from self._ask_llm(messages, None)
        except Exception:  # noqa: BLE001 - some APIs reject tool history without tool definitions
            yield ToolLimitReached()
            return
        self._decline_tool_calls(messages, unexpected_calls)
        if not reply_text:
            yield ToolLimitReached()

    @staticmethod
    def _decline_tool_calls(messages: list[Message], tool_calls: list[ToolCall]) -> None:
        for call in tool_calls:
            messages.append(Message.from_text("tool", TOOL_LIMIT_RESULT, tool_call_id=call.id))

    def _run_tool(self, call: ToolCall) -> str:
        tool = self._tools.get(call.name)
        if tool is None:
            return f"Error: unknown tool '{call.name}'"
        try:
            return tool.run(call.arguments)
        except Exception as exc:  # noqa: BLE001 - surfaced to the LLM instead of crashing the chat
            return f"Error calling tool '{call.name}': {exc}"
