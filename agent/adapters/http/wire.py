"""Transport DTOs for the HTTP boundary, shared by the server and its clients (D-035)."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

from agent.domain.event import Event, TextDelta, ToolLimitReached, ToolStarted


class CreateSessionBody(BaseModel):
    owner: str


class CreateSessionResponse(BaseModel):
    session_id: str


class SendMessageBody(BaseModel):
    text: str


class TextDeltaPayload(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    text: str


class ToolStartedPayload(BaseModel):
    type: Literal["tool_started"] = "tool_started"
    name: str
    arguments: dict[str, Any]


class ToolLimitReachedPayload(BaseModel):
    type: Literal["tool_limit_reached"] = "tool_limit_reached"


class TurnCompletedPayload(BaseModel):
    """Transport only: the turn finished and was saved."""

    type: Literal["turn_completed"] = "turn_completed"


class TurnFailedPayload(BaseModel):
    """Transport only: the turn failed after the stream started, so it was not saved."""

    type: Literal["turn_failed"] = "turn_failed"
    error: str


EventPayload = Annotated[
    TextDeltaPayload
    | ToolStartedPayload
    | ToolLimitReachedPayload
    | TurnCompletedPayload
    | TurnFailedPayload,
    Field(discriminator="type"),
]
_event_payload = TypeAdapter(EventPayload)


def to_payload(event: Event) -> EventPayload:
    match event:
        case TextDelta(text):
            return TextDeltaPayload(text=text)
        case ToolStarted(name, arguments):
            return ToolStartedPayload(name=name, arguments=arguments)
        case ToolLimitReached():
            return ToolLimitReachedPayload()


def from_payload(payload: EventPayload) -> Event:
    match payload:
        case TextDeltaPayload(text=text):
            return TextDelta(text)
        case ToolStartedPayload(name=name, arguments=arguments):
            return ToolStarted(name=name, arguments=arguments)
        case ToolLimitReachedPayload():
            return ToolLimitReached()
    raise ValueError(f"{payload.type} has no domain event")


def encode_payload(payload: EventPayload) -> str:
    return payload.model_dump_json()


def decode_payload(data: str) -> EventPayload:
    return _event_payload.validate_json(data)
