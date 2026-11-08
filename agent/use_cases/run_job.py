import logging
from collections.abc import Mapping
from dataclasses import dataclass

from agent.domain.event import TextDelta
from agent.domain.interfaces import Agent, JobSource, Notifier, SessionLifecycle
from agent.domain.job import Job, Notification
from agent.domain.message import Message
from agent.domain.request import AgentRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobResult:
    session_id: str
    error: str | None = None


class NotificationError(RuntimeError):
    """At least one channel could not deliver; the others were still tried."""


class RunJob:
    """Runs a job through any Agent and delivers the answer; the agent never notifies (D-037)."""

    def __init__(
        self,
        agent: Agent,
        sessions: SessionLifecycle,
        jobs: JobSource,
        notifiers: Mapping[str, Notifier],
    ) -> None:
        self._agent = agent
        self._sessions = sessions
        self._jobs = jobs
        self._notifiers = notifiers

    def run(self, name: str) -> JobResult:
        job = self._jobs.get(name)
        missing = [channel for channel in job.channels if channel not in self._notifiers]
        if missing:
            raise ValueError(f"{name}: no notifier configured for {', '.join(missing)}")

        session_id = self._sessions.start_new(f"job:{name}")
        request = AgentRequest(session_id, Message.from_text("user", job.prompt))
        try:
            markdown = "".join(
                event.text for event in self._agent.run(request) if isinstance(event, TextDelta)
            )
        except Exception as exc:  # the failure itself is what gets delivered
            logger.exception("job %s failed", name)
            self._deliver(job, Notification(f"{name} 失敗", f"執行失敗：{exc}", session_id))
            return JobResult(session_id=session_id, error=str(exc))

        self._deliver(job, Notification(name, markdown, session_id))
        return JobResult(session_id=session_id)

    def _deliver(self, job: Job, notification: Notification) -> None:
        failures: list[str] = []
        for channel in job.channels:
            try:
                self._notifiers[channel].send(notification)
            except Exception as exc:  # keep delivering to the remaining channels
                logger.exception("job %s could not notify %s", job.name, channel)
                failures.append(f"{channel}: {exc}")
        if failures:
            raise NotificationError("; ".join(failures))
