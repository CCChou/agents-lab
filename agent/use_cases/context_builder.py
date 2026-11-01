from agent.domain.agent_spec import AgentSpec
from agent.domain.interfaces import ConversationStore
from agent.domain.message import Message

CLEARED_TOOL_RESULT = "[已清除 {name} 的舊結果，當時的參數：{arguments}。需要時請重新呼叫工具。]"


class ContextBuilder:
    def __init__(self, store: ConversationStore) -> None:
        self._store = store

    def build(self, spec: AgentSpec, session_id: str) -> list[Message]:
        history = self._clear_old_tool_results(self._store.load(session_id))
        if spec.system_prompt:
            return [Message.from_text("system", spec.system_prompt), *history]
        return history

    @staticmethod
    def _clear_old_tool_results(history: list[Message]) -> list[Message]:
        latest_turn = max((i for i, m in enumerate(history) if m.role == "user"), default=0)
        calls = {call.id: call for m in history[:latest_turn] for call in m.tool_calls or []}

        cleared = list(history)
        for index, message in enumerate(history[:latest_turn]):
            if message.role == "tool":
                call = calls[message.tool_call_id]
                text = CLEARED_TOOL_RESULT.format(name=call.name, arguments=call.arguments)
                cleared[index] = Message.from_text("tool", text, tool_call_id=call.id)
        return cleared
