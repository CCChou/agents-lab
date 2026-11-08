"""HTTP entry adapter: sessions and SSE event streams over the Agent interface (D-035)."""

import logging
from collections.abc import AsyncIterator, Iterator

from fastapi import FastAPI, status
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool

from agent.adapters.http.wire import (
    CreateSessionBody,
    CreateSessionResponse,
    EventPayload,
    SendMessageBody,
    TurnCompletedPayload,
    TurnFailedPayload,
    encode_payload,
    to_payload,
)
from agent.domain.interfaces import Agent
from agent.domain.message import Message
from agent.domain.request import AgentRequest
from agent.use_cases.session_manager import SessionManager

logger = logging.getLogger(__name__)


def _sse_frame(payload: EventPayload) -> str:
    return f"data: {encode_payload(payload)}\n\n"


def stream_turn(agent: Agent, request: AgentRequest) -> Iterator[str]:
    """Yield one SSE frame per event. Closing it early stops the turn before it is saved."""
    try:
        for event in agent.run(request):
            yield _sse_frame(to_payload(event))
    except Exception as exc:  # the stream has started, so report the failure in-band
        logger.exception("turn failed for session %s", request.session_id)
        yield _sse_frame(TurnFailedPayload(error=str(exc)))
        return
    yield _sse_frame(TurnCompletedPayload())


async def _close_when_done(frames: Iterator[str]) -> AsyncIterator[str]:
    try:
        async for frame in iterate_in_threadpool(frames):
            yield frame
    finally:
        frames.close()  # a disconnected client must not leave the turn half-run and saved


def create_app(agent: Agent, sessions: SessionManager) -> FastAPI:
    app = FastAPI(title="agents-lab")

    @app.post("/sessions", status_code=status.HTTP_201_CREATED)
    def create_session(body: CreateSessionBody) -> CreateSessionResponse:
        return CreateSessionResponse(session_id=sessions.start_new(body.owner))

    @app.post("/sessions/{session_id}/messages")
    def send_message(session_id: str, body: SendMessageBody) -> StreamingResponse:
        request = AgentRequest(session_id, Message.from_text("user", body.text))
        return StreamingResponse(
            _close_when_done(stream_turn(agent, request)), media_type="text/event-stream"
        )

    return app
