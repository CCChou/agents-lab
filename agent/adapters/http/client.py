"""Clients of the HTTP API: the CLI uses these in place of LoopAgent and SessionManager (D-035)."""

from collections.abc import Iterator

import httpx

from agent.adapters.http.wire import (
    CreateSessionBody,
    CreateSessionResponse,
    SendMessageBody,
    TurnCompletedPayload,
    TurnFailedPayload,
    decode_payload,
    from_payload,
)
from agent.domain.event import Event
from agent.domain.request import AgentRequest

SSE_DATA_PREFIX = "data: "


class RemoteTurnError(RuntimeError):
    """The server reported, or the stream showed, that the turn did not complete."""


class RemoteSessions:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client
        self._current: dict[str, str] = {}

    def current_or_start(self, owner_id: str) -> str:
        return self._current.get(owner_id) or self.start_new(owner_id)

    def start_new(self, owner_id: str) -> str:
        body = CreateSessionBody(owner=owner_id)
        response = self._client.post("/sessions", json=body.model_dump())
        response.raise_for_status()
        session_id = CreateSessionResponse.model_validate(response.json()).session_id
        self._current[owner_id] = session_id
        return session_id


class RemoteAgent:
    name = "remote"

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def run(self, request: AgentRequest) -> Iterator[Event]:
        body = SendMessageBody(text=request.message.text)
        with self._client.stream(
            "POST",
            f"/sessions/{request.session_id}/messages",
            json=body.model_dump(),
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith(SSE_DATA_PREFIX):
                    continue
                match decode_payload(line.removeprefix(SSE_DATA_PREFIX)):
                    case TurnCompletedPayload():
                        return
                    case TurnFailedPayload(error=error):
                        raise RemoteTurnError(error)
                    case payload:
                        yield from_payload(payload)
        raise RemoteTurnError("the stream ended before the turn completed")
