from collections.abc import Iterator

from fastapi.testclient import TestClient

from agent.adapters.http.api import create_app, stream_turn
from agent.adapters.http.wire import (
    TextDeltaPayload,
    ToolStartedPayload,
    TurnCompletedPayload,
    TurnFailedPayload,
    decode_payload,
)
from agent.adapters.in_memory_store import InMemorySessionStore
from agent.domain.agent_spec import AgentSpec
from agent.domain.event import Event, TextDelta, ToolStarted
from agent.domain.job import UnknownJobError
from agent.domain.message import Message
from agent.domain.request import AgentRequest
from agent.use_cases.context_builder import ContextBuilder
from agent.use_cases.loop_agent import LoopAgent
from agent.use_cases.run_job import JobResult, NotificationError
from agent.use_cases.session_manager import SessionManager
from agent.use_cases.tool_registry import ToolRegistry


class RecordingLLMClient:
    def __init__(self, replies: list[str] | None = None) -> None:
        self.calls: list[list[Message]] = []
        self._replies = replies or ["Hel", "lo"]

    def stream(self, messages: list[Message], tools=None) -> Iterator[str]:
        self.calls.append(list(messages))
        yield from self._replies


class FailingLLMClient:
    def stream(self, messages: list[Message], tools=None) -> Iterator[str]:
        raise RuntimeError("connection lost")
        yield  # pragma: no cover


class ScriptedAgent:
    name = "scripted"

    def __init__(self, events: list[Event]) -> None:
        self._events = events

    def run(self, request: AgentRequest) -> Iterator[Event]:
        yield from self._events


def make_client(llm_client=None, agent=None) -> tuple[TestClient, InMemorySessionStore]:
    store = InMemorySessionStore()
    agent = agent or LoopAgent(
        AgentSpec(name="test"),
        llm_client or RecordingLLMClient(),
        store,
        ContextBuilder(store),
        ToolRegistry([]),
    )
    return TestClient(create_app(agent, SessionManager(store, store))), store


def parse_sse(body: str) -> list:
    return [
        decode_payload(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


def create_session(client: TestClient, owner: str = "cli") -> str:
    response = client.post("/sessions", json={"owner": owner})
    assert response.status_code == 201
    return response.json()["session_id"]


def send(client: TestClient, session_id: str, text: str):
    return client.post(f"/sessions/{session_id}/messages", json={"text": text})


def test_create_session_starts_a_new_current_session_for_the_owner():
    client, store = make_client()

    first = create_session(client, "web")
    second = create_session(client, "web")

    assert first != second
    assert store.current("web") == second


def test_send_message_streams_events_and_ends_with_turn_completed():
    client, _ = make_client()
    session_id = create_session(client)

    response = send(client, session_id, "hi")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert parse_sse(response.text) == [
        TextDeltaPayload(text="Hel"),
        TextDeltaPayload(text="lo"),
        TurnCompletedPayload(),
    ]


def test_send_message_forwards_tool_events():
    agent = ScriptedAgent([ToolStarted(name="lookup", arguments={"q": "x"}), TextDelta("ok")])
    client, _ = make_client(agent=agent)

    payloads = parse_sse(send(client, create_session(client), "hi").text)

    assert payloads[0] == ToolStartedPayload(name="lookup", arguments={"q": "x"})


def test_messages_in_the_same_session_continue_the_conversation():
    llm_client = RecordingLLMClient()
    client, _ = make_client(llm_client)
    session_id = create_session(client)

    send(client, session_id, "first")
    send(client, session_id, "second")

    assert [m.text for m in llm_client.calls[-1] if m.role == "user"] == ["first", "second"]


def test_sessions_do_not_share_history():
    llm_client = RecordingLLMClient()
    client, _ = make_client(llm_client)

    send(client, create_session(client), "first")
    send(client, create_session(client), "second")

    assert [m.text for m in llm_client.calls[-1] if m.role == "user"] == ["second"]


def test_a_failed_turn_is_reported_in_the_stream_and_not_saved():
    client, store = make_client(FailingLLMClient())
    session_id = create_session(client)

    response = send(client, session_id, "hi")

    assert parse_sse(response.text) == [TurnFailedPayload(error="connection lost")]
    assert store.load(session_id) == []


def test_closing_the_stream_early_does_not_save_the_turn():
    store = InMemorySessionStore()
    agent = LoopAgent(
        AgentSpec(name="test"), RecordingLLMClient(), store, ContextBuilder(store), ToolRegistry([])
    )
    frames = stream_turn(agent, AgentRequest("s1", Message.from_text("user", "hi")))

    next(frames)
    frames.close()

    assert store.load("s1") == []


def test_send_message_requires_text():
    client, _ = make_client()

    response = client.post(f"/sessions/{create_session(client)}/messages", json={})

    assert response.status_code == 422


# --- jobs (D-037) ---


class FakeRunJob:
    def __init__(self, outcome) -> None:
        self._outcome = outcome
        self.names: list[str] = []

    def run(self, name: str):
        self.names.append(name)
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def job_client(outcome) -> tuple[TestClient, FakeRunJob]:
    store = InMemorySessionStore()
    run_job = FakeRunJob(outcome)
    app = create_app(ScriptedAgent([]), SessionManager(store, store), run_job=run_job)
    return TestClient(app), run_job


def test_run_job_returns_the_session_when_it_was_delivered():
    client, run_job = job_client(JobResult(session_id="s1"))

    response = client.post("/jobs/daily-digest/run")

    assert run_job.names == ["daily-digest"]
    assert response.status_code == 200
    assert response.json() == {"session_id": "s1", "error": None}


def test_run_job_reports_502_when_the_agent_failed_but_the_notice_went_out():
    client, _ = job_client(JobResult(session_id="s1", error="rate limited"))

    response = client.post("/jobs/daily-digest/run")

    assert response.status_code == 502
    assert response.json() == {"session_id": "s1", "error": "rate limited"}


def test_run_job_reports_404_for_an_unknown_job():
    client, _ = job_client(UnknownJobError("nope: not defined"))

    response = client.post("/jobs/nope/run")

    assert response.status_code == 404
    assert response.json() == {"session_id": None, "error": "nope: not defined"}


def test_run_job_reports_500_when_delivery_or_configuration_failed():
    for error in (NotificationError("slack: down"), ValueError("no notifier for mail")):
        client, _ = job_client(error)

        response = client.post("/jobs/daily-digest/run")

        assert response.status_code == 500
        assert response.json()["error"] == str(error)


def test_jobs_are_not_served_when_no_runner_is_configured():
    client, _ = make_client()

    assert client.post("/jobs/daily-digest/run").status_code == 404
