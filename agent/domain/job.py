from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    """A scheduled task: what to ask the agent and where to deliver the answer (D-037)."""

    name: str
    prompt: str
    channels: tuple[str, ...]


@dataclass(frozen=True)
class Notification:
    title: str
    markdown: str
    session_id: str


class UnknownJobError(LookupError):
    pass
