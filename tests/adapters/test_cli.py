import io
from collections.abc import Iterator

from agent.adapters.cli import (
    ERROR_PREFIX,
    GOODBYE_MESSAGE,
    PROMPT,
    TOOL_LIMIT_NOTICE,
    WELCOME_MESSAGE,
    run,
)
from agent.adapters.in_memory_store import InMemoryConversationStore
from agent.domain.agent_spec import AgentSpec
from agent.domain.event import Event, ToolLimitReached, ToolStarted
from agent.domain.message import Message
from agent.domain.request import AgentRequest
from agent.use_cases.context_builder import ContextBuilder
from agent.use_cases.loop_agent import LoopAgent
from agent.use_cases.tool_registry import ToolRegistry


def make_agent(llm_client) -> LoopAgent:
    store = InMemoryConversationStore()
    spec = AgentSpec(name="test")
    return LoopAgent(spec, llm_client, store, ContextBuilder(store), ToolRegistry([]))


class FakeLLMClient:
    def stream(self, messages: list[Message], tools=None) -> Iterator[str]:
        yield f"echo: {messages[-1].text}"


class ChunkedFakeLLMClient:
    def stream(self, messages: list[Message], tools=None) -> Iterator[str]:
        yield "Hel"
        yield "lo"


class FailsOnceFakeLLMClient:
    def __init__(self) -> None:
        self._failed = False

    def stream(self, messages: list[Message], tools=None) -> Iterator[str]:
        if not self._failed:
            self._failed = True
            raise RuntimeError("connection lost")
        yield "recovered"


class ScriptedAgent:
    name = "scripted"

    def __init__(self, events: list[Event]) -> None:
        self._events = events
        self.requests: list[AgentRequest] = []

    def run(self, request: AgentRequest) -> Iterator[Event]:
        self.requests.append(request)
        yield from self._events


def test_run_prints_welcome_message_first_and_goodbye_message_last():
    agent = make_agent(FakeLLMClient())
    output = io.StringIO()

    run(agent, [], output)

    assert output.getvalue() == WELCOME_MESSAGE + PROMPT + GOODBYE_MESSAGE


def test_run_sends_each_line_to_chat_and_prints_the_reply():
    agent = make_agent(FakeLLMClient())
    output = io.StringIO()

    run(agent, ["hello", "world"], output)

    assert output.getvalue() == (
        WELCOME_MESSAGE
        + PROMPT
        + "echo: hello\n"
        + PROMPT
        + "echo: world\n"
        + PROMPT
        + GOODBYE_MESSAGE
    )


def test_run_writes_each_chunk_as_it_arrives():
    agent = make_agent(ChunkedFakeLLMClient())
    output = io.StringIO()

    run(agent, ["hi"], output)

    assert output.getvalue() == WELCOME_MESSAGE + PROMPT + "Hello\n" + PROMPT + GOODBYE_MESSAGE


def test_run_stops_on_exit_command():
    agent = make_agent(FakeLLMClient())
    output = io.StringIO()

    run(agent, ["hello", "exit", "should not be sent"], output)

    assert output.getvalue() == (
        WELCOME_MESSAGE + PROMPT + "echo: hello\n" + PROMPT + GOODBYE_MESSAGE
    )


def test_run_skips_blank_lines():
    agent = make_agent(FakeLLMClient())
    output = io.StringIO()

    run(agent, ["", "   ", "hi"], output)

    assert output.getvalue() == (
        WELCOME_MESSAGE + PROMPT + PROMPT + PROMPT + "echo: hi\n" + PROMPT + GOODBYE_MESSAGE
    )


def test_run_prints_a_prompt_before_reading_each_line():
    agent = make_agent(FakeLLMClient())
    output = io.StringIO()

    run(agent, ["hello"], output)

    assert PROMPT in output.getvalue()


def test_run_sends_every_line_in_the_same_session():
    agent = ScriptedAgent([])

    run(agent, ["hello", "world"], io.StringIO())

    assert [r.message for r in agent.requests] == [
        Message.from_text("user", "hello"),
        Message.from_text("user", "world"),
    ]
    assert agent.requests[0].session_id == agent.requests[1].session_id


def test_run_announces_tool_use():
    agent = ScriptedAgent([ToolStarted(name="lookup", arguments={"q": "x"})])
    output = io.StringIO()

    run(agent, ["hi"], output)

    assert "[使用工具: lookup arguments={'q': 'x'}]" in output.getvalue()


def test_run_reports_when_the_tool_limit_is_reached():
    agent = ScriptedAgent([ToolLimitReached()])
    output = io.StringIO()

    run(agent, ["hi"], output)

    assert TOOL_LIMIT_NOTICE in output.getvalue()


def test_run_reports_llm_errors_and_keeps_the_session_alive():
    agent = make_agent(FailsOnceFakeLLMClient())
    output = io.StringIO()

    run(agent, ["hello", "again"], output)

    assert output.getvalue() == (
        WELCOME_MESSAGE
        + PROMPT
        + f"{ERROR_PREFIX}connection lost\n"
        + PROMPT
        + "recovered\n"
        + PROMPT
        + GOODBYE_MESSAGE
    )
