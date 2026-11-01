from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest

from agent.adapters.miniflux import (
    MIN_STORED_CHARS,
    MinifluxArticleReader,
    MinifluxGetEntryTool,
    MinifluxQueryTool,
)
from agent.domain.interfaces import ArticleReader
from agent.domain.tool import Tool

NEWEST_FIRST = {"order": "published_at", "direction": "desc"}


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
        "published_at": "2026-11-01T14:00:00Z",
        "content": "<p>Article body</p>",
        "feed": {"id": 1, "title": feed_title},
    }


def test_satisfies_tool_port():
    tool = MinifluxQueryTool(client=FakeHttpClient(responses={}))

    assert isinstance(tool, Tool)


def test_date_range_descriptions_explain_the_expected_offset():
    properties = MinifluxQueryTool.parameters_schema["properties"]

    assert "get_current_time" in properties["published_after"]["description"]
    assert "get_current_time" in properties["published_before"]["description"]


def test_run_queries_entries_with_default_limit():
    http_client = FakeHttpClient(responses={"/v1/entries": _response({"entries": [_entry()]})})
    tool = MinifluxQueryTool(client=http_client)

    tool.run({})

    assert http_client.requests == [("/v1/entries", NEWEST_FIRST | {"limit": 10})]


def test_run_caps_the_limit():
    http_client = FakeHttpClient(responses={"/v1/entries": _response({"entries": []})})
    tool = MinifluxQueryTool(client=http_client)

    tool.run({"limit": 21})

    assert http_client.requests[0][1]["limit"] == 20


def test_run_passes_status_and_search_and_custom_limit():
    http_client = FakeHttpClient(responses={"/v1/entries": _response({"entries": []})})
    tool = MinifluxQueryTool(client=http_client)

    tool.run({"status": "unread", "search": "python", "limit": 5})

    assert http_client.requests == [
        ("/v1/entries", NEWEST_FIRST | {"limit": 5, "status": "unread", "search": "python"})
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
    assert ("/v1/feeds/7/entries", NEWEST_FIRST | {"limit": 10}) in http_client.requests


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


def test_run_shows_the_published_time_in_the_given_timezone():
    http_client = FakeHttpClient(responses={"/v1/entries": _response({"entries": [_entry()]})})
    tool = MinifluxQueryTool(client=http_client, tz=timezone(timedelta(hours=8)))

    result = tool.run({})

    assert "2026-11-01T22:00:00+08:00" in result


def test_run_reports_when_no_entries_found():
    http_client = FakeHttpClient(responses={"/v1/entries": _response({"entries": []})})
    tool = MinifluxQueryTool(client=http_client)

    result = tool.run({})

    assert result == "No entries found."


def test_get_entry_satisfies_tool_port():
    assert isinstance(MinifluxGetEntryTool(client=FakeHttpClient(responses={})), Tool)


def test_get_entry_returns_metadata_and_the_body_as_untrusted_content():
    http_client = FakeHttpClient(responses={"/v1/entries/42": _response(_entry(id=42))})
    tool = MinifluxGetEntryTool(client=http_client, tz=timezone(timedelta(hours=8)))

    result = tool.run({"entry_id": 42})

    assert "Title: Some Article" in result
    assert "Feed: Some Feed" in result
    assert "Published: 2026-11-01T22:00:00+08:00" in result
    assert "URL: https://example.test/42" in result
    assert "<untrusted_content>\nArticle body\n</untrusted_content>" in result


def test_get_entry_reads_from_the_given_offset():
    http_client = FakeHttpClient(responses={"/v1/entries/1": _response(_entry())})
    tool = MinifluxGetEntryTool(client=http_client)

    assert "<untrusted_content>\nbody\n" in tool.run({"entry_id": 1, "offset": 8})


def test_get_entry_raises_on_http_errors():
    http_client = FakeHttpClient(responses={"/v1/entries/9": _response({}, status_code=404)})
    tool = MinifluxGetEntryTool(client=http_client)

    with pytest.raises(httpx.HTTPStatusError):
        tool.run({"entry_id": 9})


def _entry_with_content(content: str) -> dict:
    return _entry() | {"content": content}


def _reader(content: str, read_page) -> MinifluxArticleReader:
    http_client = FakeHttpClient(
        responses={"/v1/entries/1": _response(_entry_with_content(content))}
    )
    return MinifluxArticleReader(
        client=http_client, read_page=read_page, tz=timezone(timedelta(hours=8))
    )


def test_reader_satisfies_article_reader_port():
    assert isinstance(_reader("", lambda url: ""), ArticleReader)


def test_reader_returns_the_article_metadata():
    article = _reader("<p>Body</p>", lambda url: "Page").read(1)

    assert article.title == "Some Article"
    assert article.feed == "Some Feed"
    assert article.published_at == "2026-11-01T22:00:00+08:00"
    assert article.url == "https://example.test/1"


def test_reader_uses_stored_content_when_it_is_long_enough():
    stored = "a" * MIN_STORED_CHARS

    article = _reader(f"<p>{stored}</p>", lambda url: pytest.fail("should not fetch")).read(1)

    assert article.text == stored


def test_reader_reads_the_page_when_stored_content_is_short():
    urls: list[str] = []

    def read_page(url: str) -> str:
        urls.append(url)
        return "Full article text"

    article = _reader("<p>Short</p>", read_page).read(1)

    assert article.text == "Full article text"
    assert urls == ["https://example.test/1"]


def test_reader_keeps_stored_content_when_the_page_cannot_be_read():
    def read_page(url: str) -> str:
        raise ValueError("blocked")

    assert _reader("<p>Short</p>", read_page).read(1).text == "Short"


def test_reader_keeps_stored_content_when_the_page_is_shorter():
    assert _reader("<p>Stored excerpt</p>", lambda url: "x").read(1).text == "Stored excerpt"
