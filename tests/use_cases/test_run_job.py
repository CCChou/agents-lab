from collections.abc import Iterator

import pytest

from agent.domain.event import Event, TextDelta, ToolStarted
from agent.domain.job import Job, Notification, UnknownJobError
from agent.domain.request import AgentRequest
from agent.use_cases.run_job import JobResult, NotificationError, RunJob

JOB = Job(name="daily", prompt="今天的趨勢", channels=("slack", "mail"))


class FakeJobs:
    def __init__(self, *jobs: Job) -> None:
        self._jobs = {job.name: job for job in jobs}

    def get(self, name: str) -> Job:
        if name not in self._jobs:
            raise UnknownJobError(name)
        return self._jobs[name]


class FakeSessions:
    def __init__(self) -> None:
        self.started: list[str] = []

    def current_or_start(self, owner_id: str) -> str:
        raise AssertionError("jobs always start a fresh session")

    def start_new(self, owner_id: str) -> str:
        self.started.append(owner_id)
        return f"s{len(self.started)}"


class ScriptedAgent:
    name = "scripted"

    def __init__(self, events: list[Event], error: Exception | None = None) -> None:
        self._events = events
        self._error = error
        self.requests: list[AgentRequest] = []

    def run(self, request: AgentRequest) -> Iterator[Event]:
        self.requests.append(request)
        yield from self._events
        if self._error:
            raise self._error


class RecordingNotifier:
    def __init__(self, error: Exception | None = None) -> None:
        self.sent: list[Notification] = []
        self._error = error

    def send(self, notification: Notification) -> None:
        if self._error:
            raise self._error
        self.sent.append(notification)


def make_run_job(agent, notifiers=None, jobs=None) -> tuple[RunJob, FakeSessions, dict]:
    notifiers = notifiers or {"slack": RecordingNotifier(), "mail": RecordingNotifier()}
    sessions = FakeSessions()
    return RunJob(agent, sessions, jobs or FakeJobs(JOB), notifiers), sessions, notifiers


def test_run_asks_the_agent_the_job_prompt_in_a_fresh_job_session():
    agent = ScriptedAgent([TextDelta("ok")])
    run_job, sessions, _ = make_run_job(agent)

    result = run_job.run("daily")

    assert sessions.started == ["job:daily"]
    assert agent.requests[0].session_id == "s1"
    assert agent.requests[0].message.text == "今天的趨勢"
    assert result == JobResult(session_id="s1")


def test_run_delivers_the_whole_answer_to_every_channel():
    agent = ScriptedAgent(
        [ToolStarted(name="q", arguments={}), TextDelta("## 趨勢\n"), TextDelta("…")]
    )
    run_job, _, notifiers = make_run_job(agent)

    run_job.run("daily")

    expected = Notification(title="daily", markdown="## 趨勢\n…", session_id="s1")
    assert notifiers["slack"].sent == [expected]
    assert notifiers["mail"].sent == [expected]


def test_a_failed_agent_run_is_delivered_as_a_failure_notice():
    agent = ScriptedAgent([TextDelta("partial")], error=RuntimeError("rate limited"))
    run_job, _, notifiers = make_run_job(agent)

    result = run_job.run("daily")

    assert result == JobResult(session_id="s1", error="rate limited")
    notice = notifiers["slack"].sent[0]
    assert notice.title == "daily 失敗"
    assert "rate limited" in notice.markdown
    assert "partial" not in notice.markdown


def test_unknown_jobs_are_reported_without_running_anything():
    agent = ScriptedAgent([])
    run_job, sessions, _ = make_run_job(agent)

    with pytest.raises(UnknownJobError):
        run_job.run("missing")
    assert sessions.started == []


def test_a_job_with_an_unconfigured_channel_fails_before_running():
    agent = ScriptedAgent([TextDelta("ok")])
    run_job, sessions, _ = make_run_job(agent, notifiers={"slack": RecordingNotifier()})

    with pytest.raises(ValueError, match="mail"):
        run_job.run("daily")
    assert agent.requests == []
    assert sessions.started == []


def test_a_failing_channel_does_not_stop_the_others_and_is_reported():
    broken = RecordingNotifier(error=ConnectionError("slack is down"))
    working = RecordingNotifier()
    run_job, _, _ = make_run_job(
        ScriptedAgent([TextDelta("ok")]), {"slack": broken, "mail": working}
    )

    with pytest.raises(NotificationError, match="slack is down"):
        run_job.run("daily")
    assert len(working.sent) == 1
