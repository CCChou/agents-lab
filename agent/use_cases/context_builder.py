from agent.domain.agent_spec import AgentSpec
from agent.domain.interfaces import ConversationStore
from agent.domain.message import Message


class ContextBuilder:
    def __init__(self, store: ConversationStore) -> None:
        self._store = store

    def build(self, spec: AgentSpec, session_id: str) -> list[Message]:
        history = self._store.load(session_id)
        if spec.system_prompt:
            return [Message.from_text("system", spec.system_prompt), *history]
        return history
