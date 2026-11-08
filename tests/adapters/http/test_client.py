import json

import httpx
import pytest

from agent.adapters.http.client import RemoteAgent, RemoteSessions, RemoteTurnError
from agent.domain.event import TextDelta, ToolLimitReached, ToolStarted
from agent.domain.interfaces import Agent, SessionLifecycle
from agent.domain.message import Message
from agent.domain.request import AgentRequest


def sse(*payloads: dict) -> str:
    return "".join(f"data: {json.dumps(payload)}\n\n" for payload in payloads)


def client_for(handler) -> httpx.Client:
    return httpx.Client(base_url="http://agent.test", transport=httpx.MockTransport(handler))


def request(text: str = "hi", session_id: str = "s1") -> AgentRequest:
    return AgentRequest(session_id, Message.from_text("user", text))


# --- RemoteSessions ---


def test_remote_sessions_satisfies_session_lifecycle_port():
    assert isinstance(RemoteSessions(client_for(lambda r: httpx.Response(500))), SessionLifecycle)


def test_start_new_creates_a_session_through_the_api():
    seen: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append({"path": req.url.path, "body": json.loads(req.content)})
        return httpx.Response(201, json={"session_id": f"s{len(seen)}"})

    sessions = RemoteSessions(client_for(handler))

    assert sessions.start_new("cli") == "s1"
    assert seen == [{"path": "/sessions", "body": {"owner": "cli"}}]


def test_current_or_start_reuses_the_session_until_a_new_one_starts():
    count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(201, json={"session_id": f"s{count}"})

    sessions = RemoteSessions(client_for(handler))

    assert sessions.current_or_start("cli") == "s1"
    assert sessions.current_or_start("cli") == "s1"
    assert sessions.start_new("cli") == "s2"
    assert sessions.current_or_start("cli") == "s2"


def test_start_new_raises_when_the_server_rejects_it():
    sessions = RemoteSessions(client_for(lambda r: httpx.Response(500)))

    with pytest.raises(httpx.HTTPStatusError):
        sessions.start_new("cli")


# --- RemoteAgent ---


def test_remote_agent_satisfies_agent_port():
    assert isinstance(RemoteAgent(client_for(lambda r: httpx.Response(500))), Agent)


def test_run_posts_the_message_to_the_session():
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, text=sse({"type": "turn_completed"}))

    list(RemoteAgent(client_for(handler)).run(request("hello", "abc")))

    assert seen[0].url.path == "/sessions/abc/messages"
    assert json.loads(seen[0].content) == {"text": "hello"}


def test_run_turns_the_stream_back_into_domain_events():
    body = sse(
        {"type": "tool_started", "name": "lookup", "arguments": {"q": "x"}},
        {"type": "tool_limit_reached"},
        {"type": "text_delta", "text": "Hel"},
        {"type": "text_delta", "text": "lo"},
        {"type": "turn_completed"},
    )
    agent = RemoteAgent(client_for(lambda r: httpx.Response(200, text=body)))

    assert list(agent.run(request())) == [
        ToolStarted(name="lookup", arguments={"q": "x"}),
        ToolLimitReached(),
        TextDelta("Hel"),
        TextDelta("lo"),
    ]


def test_run_raises_when_the_turn_failed_after_yielding_earlier_events():
    body = sse({"type": "text_delta", "text": "part"}, {"type": "turn_failed", "error": "boom"})
    events = RemoteAgent(client_for(lambda r: httpx.Response(200, text=body))).run(request())

    assert next(events) == TextDelta("part")
    with pytest.raises(RemoteTurnError, match="boom"):
        next(events)


def test_run_raises_when_the_stream_ends_without_a_final_event():
    body = sse({"type": "text_delta", "text": "part"})
    agent = RemoteAgent(client_for(lambda r: httpx.Response(200, text=body)))

    with pytest.raises(RemoteTurnError, match="ended"):
        list(agent.run(request()))


def test_run_raises_when_the_server_rejects_the_request():
    agent = RemoteAgent(client_for(lambda r: httpx.Response(422, json={"detail": "bad"})))

    with pytest.raises(httpx.HTTPStatusError):
        list(agent.run(request()))


# --- CLI through the real API ---


def make_remote_cli(llm_client):
    import io

    from fastapi.testclient import TestClient

    from agent.adapters.http.api import create_app
    from agent.adapters.in_memory_store import InMemorySessionStore
    from agent.domain.agent_spec import AgentSpec
    from agent.use_cases.context_builder import ContextBuilder
    from agent.use_cases.loop_agent import LoopAgent
    from agent.use_cases.session_manager import SessionManager
    from agent.use_cases.tool_registry import ToolRegistry

    store = InMemorySessionStore()
    agent = LoopAgent(
        AgentSpec(name="test"), llm_client, store, ContextBuilder(store), ToolRegistry([])
    )
    http = TestClient(create_app(agent, SessionManager(store, store)))
    return RemoteAgent(http), RemoteSessions(http), io.StringIO()


class RecordingLLMClient:
    def __init__(self) -> None:
        self.calls: list[list[Message]] = []

    def stream(self, messages, tools=None):
        self.calls.append(list(messages))
        yield f"echo: {messages[-1].text}"


def test_cli_talks_to_the_server_and_reset_starts_a_fresh_context():
    from agent.adapters.cli import run

    llm_client = RecordingLLMClient()
    agent, sessions, output = make_remote_cli(llm_client)

    run(agent, sessions, ["old topic", "follow up", "/reset", "new topic"], output)

    assert "echo: follow up" in output.getvalue()
    assert [m.text for m in llm_client.calls[1] if m.role == "user"] == ["old topic", "follow up"]
    assert [m.text for m in llm_client.calls[-1] if m.role == "user"] == ["new topic"]


def test_cli_reports_a_failed_remote_turn_and_keeps_going():
    from agent.adapters.cli import ERROR_PREFIX, run

    class FailsOnce:
        def __init__(self) -> None:
            self.failed = False

        def stream(self, messages, tools=None):
            if not self.failed:
                self.failed = True
                raise RuntimeError("connection lost")
            yield "recovered"

    agent, sessions, output = make_remote_cli(FailsOnce())

    run(agent, sessions, ["hello", "again"], output)

    assert f"{ERROR_PREFIX}connection lost" in output.getvalue()
    assert "recovered" in output.getvalue()
