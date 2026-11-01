from datetime import UTC, datetime

import httpx
import pytest

from agent.adapters.miniflux import MinifluxQueryTool
from agent.domain.tool import Tool


class FakeHttpClient:
    def __init__(self, responses: dict[str, httpx.Response]) -> None:
        self._responses = responses
        self.requests: list[tuple[str, dict]] = []

    def get(self, path: str, params: dict | None = None) -> httpx.Response:
        self.requests.append((path, params or {}))
        return self._responses[path]


def _response(json_data, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=json_data, request=httpx.Request("GET", "http://test"))


def _entry(
    id: int = 1, title: str = "Some Article", feed_title: str = "Some Feed", status: str = "unread"
) -> dict:
    return {
        "id": id,
        "title": title,
        "url": f"https://example.test/{id}",
        "status": status,
        "feed": {"id": 1, "title": feed_title},
    }


def test_satisfies_tool_port():
    tool = MinifluxQueryTool(client=FakeHttpClient(responses={}))

    assert isinstance(tool, Tool)


def test_run_queries_entries_with_default_limit():
    http_client = FakeHttpClient(responses={"/v1/entries": _response({"entries": [_entry()]})})
    tool = MinifluxQueryTool(client=http_client)

    tool.run({})

    assert http_client.requests == [("/v1/entries", {"limit": 10})]


def test_run_passes_status_and_search_and_custom_limit():
    http_client = FakeHttpClient(responses={"/v1/entries": _response({"entries": []})})
    tool = MinifluxQueryTool(client=http_client)

    tool.run({"status": "unread", "search": "python", "limit": 5})

    assert http_client.requests == [
        ("/v1/entries", {"limit": 5, "status": "unread", "search": "python"})
    ]


def test_run_converts_published_after_and_before_to_unix_timestamps():
    http_client = FakeHttpClient(responses={"/v1/entries": _response({"entries": []})})
    tool = MinifluxQueryTool(client=http_client)

    tool.run(
        {
            "published_after": "2026-08-20T00:00:00+00:00",
            "published_before": "2026-08-24T00:00:00+00:00",
        }
    )

    _, params = http_client.requests[0]
    expected_after = int(datetime(2026, 8, 20, tzinfo=UTC).timestamp())
    expected_before = int(datetime(2026, 8, 24, tzinfo=UTC).timestamp())
    assert params["published_after"] == expected_after
    assert params["published_before"] == expected_before


def test_run_resolves_feed_name_to_id_and_queries_the_feed_scoped_endpoint():
    http_client = FakeHttpClient(
        responses={
            "/v1/feeds": _response(
                [{"id": 7, "title": "Hacker News"}, {"id": 8, "title": "Lobsters"}]
            ),
            "/v1/feeds/7/entries": _response({"entries": [_entry(feed_title="Hacker News")]}),
        }
    )
    tool = MinifluxQueryTool(client=http_client)

    tool.run({"feed_name": "hacker"})

    assert ("/v1/feeds", {}) in http_client.requests
    assert ("/v1/feeds/7/entries", {"limit": 10}) in http_client.requests


def test_run_raises_when_no_feed_matches_the_given_name():
    http_client = FakeHttpClient(
        responses={"/v1/feeds": _response([{"id": 7, "title": "Hacker News"}])}
    )
    tool = MinifluxQueryTool(client=http_client)

    with pytest.raises(ValueError, match="nonexistent"):
        tool.run({"feed_name": "nonexistent"})


def test_run_formats_entries_as_readable_text():
    http_client = FakeHttpClient(
        responses={
            "/v1/entries": _response(
                {"entries": [_entry(id=42, title="Great Article", feed_title="Cool Feed")]}
            )
        }
    )
    tool = MinifluxQueryTool(client=http_client)

    result = tool.run({})

    assert "Great Article" in result
    assert "Cool Feed" in result
    assert "https://example.test/42" in result


def test_run_reports_when_no_entries_found():
    http_client = FakeHttpClient(responses={"/v1/entries": _response({"entries": []})})
    tool = MinifluxQueryTool(client=http_client)

    result = tool.run({})

    assert result == "No entries found."
