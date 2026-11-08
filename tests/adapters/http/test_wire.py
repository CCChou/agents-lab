import json

import pytest

from agent.adapters.http.wire import (
    TurnCompletedPayload,
    TurnFailedPayload,
    decode_payload,
    encode_payload,
    from_payload,
    to_payload,
)
from agent.domain.event import TextDelta, ToolLimitReached, ToolStarted

EVENTS = [
    TextDelta("你好"),
    ToolStarted(name="miniflux_query_entries", arguments={"limit": 15, "category_name": "Tech"}),
    ToolLimitReached(),
]


@pytest.mark.parametrize("event", EVENTS)
def test_every_event_survives_a_round_trip_through_json(event):
    assert from_payload(decode_payload(encode_payload(to_payload(event)))) == event


def test_payloads_carry_a_type_tag():
    encoded = [json.loads(encode_payload(to_payload(event))) for event in EVENTS]

    assert [payload["type"] for payload in encoded] == [
        "text_delta",
        "tool_started",
        "tool_limit_reached",
    ]


def test_text_delta_keeps_non_ascii_text_readable():
    assert "你好" in encode_payload(to_payload(TextDelta("你好")))


def test_transport_only_payloads_round_trip():
    failed = TurnFailedPayload(error="connection lost")

    assert decode_payload(encode_payload(TurnCompletedPayload())) == TurnCompletedPayload()
    assert decode_payload(encode_payload(failed)) == failed


def test_transport_only_payloads_have_no_domain_event():
    with pytest.raises(ValueError):
        from_payload(TurnCompletedPayload())


def test_decode_rejects_an_unknown_type():
    with pytest.raises(ValueError):
        decode_payload('{"type": "unknown"}')
