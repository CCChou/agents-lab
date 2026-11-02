from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest

from agent.adapters.miniflux import (
    MIN_STORED_CHARS,
    MinifluxArticleReader,
    MinifluxCountEntriesByCategoryTool,
    MinifluxGetEntryTool,
    MinifluxListCategoriesTool,
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
    if isinstance(json_data, dict) and "entries" in json_data:
        json_data = {"total": len(json_data["entries"]), **json_data}
    return httpx.Response(status_code, json=json_data, request=httpx.Request("GET", "http://test"))


def _entry(
    id: int = 1,
    title: str | None = None,
    feed_title: str = "Some Feed",
    status: str = "unread",
    category: str = "Some Category",
) -> dict:
    return {
        "id": id,
        "title": title or ("Some Article" if id == 1 else f"Some Article {id}"),
        "url": f"https://example.test/{id}",
        "status": status,
        "published_at": "2026-11-01T14:00:00Z",
        "content": "<p>Article body</p>",
        "feed": {"id": 1, "title": feed_title, "category": {"id": 1, "title": category}},
    }


def test_satisfies_tool_port():
    tool = MinifluxQueryTool(client=FakeHttpClient(responses={}))

    assert isinstance(tool, Tool)


def test_date_range_descriptions_explain_the_expected_offset():
    properties = MinifluxQueryTool.parameters_schema["properties"]

    assert "get_current_time" in properties["published_after"]["description"]
    assert "get_current_time" in properties["published_before"]["description"]


def test_limit_description_explains_the_hard_cap_and_paging():
    description = MinifluxQueryTool.parameters_schema["properties"]["limit"]["description"]

    assert "Larger values are reduced to 15" in description
    assert "use offset to read more" in description


def test_run_queries_entries_with_default_limit():
    http_client = FakeHttpClient(responses={"/v1/entries": _response({"entries": [_entry()]})})
    tool = MinifluxQueryTool(client=http_client)

    tool.run({})

    assert http_client.requests == [("/v1/entries", NEWEST_FIRST | {"limit": 10})]


def test_run_caps_the_limit():
    http_client = FakeHttpClient(responses={"/v1/entries": _response({"entries": []})})
    tool = MinifluxQueryTool(client=http_client)

    tool.run({"limit": 16})

    assert http_client.requests[0][1]["limit"] == 15


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


def _categories_client(entries_by_category: dict[int, dict]) -> FakeHttpClient:
    return FakeHttpClient(
        responses={
            "/v1/categories": _response(
                [
                    {"id": 1, "title": "News - IT"},
                    {"id": 2, "title": "News - World"},
                    {"id": 3, "title": "Tech - Architecture"},
                ]
            ),
            **{
                f"/v1/categories/{category_id}/entries": _response(page)
                for category_id, page in entries_by_category.items()
            },
        }
    )


def test_run_queries_every_category_starting_with_the_name_case_insensitively():
    http_client = _categories_client({1: {"entries": []}, 2: {"entries": []}})
    tool = MinifluxQueryTool(client=http_client)

    tool.run({"category_name": "news", "status": "unread"})

    params = NEWEST_FIRST | {"limit": 10, "status": "unread"}
    assert ("/v1/categories/1/entries", params) in http_client.requests
    assert ("/v1/categories/2/entries", params) in http_client.requests
    assert not any(path == "/v1/categories/3/entries" for path, _ in http_client.requests)


def test_run_matches_the_start_of_the_category_name_rather_than_any_part():
    http_client = FakeHttpClient(
        responses={"/v1/categories": _response([{"id": 3, "title": "Tech - Architecture"}])}
    )
    tool = MinifluxQueryTool(client=http_client)

    with pytest.raises(ValueError, match="miniflux_list_categories"):
        tool.run({"category_name": "it"})


def test_run_applies_the_limit_to_each_category_and_takes_turns():
    http_client = _categories_client(
        {
            1: {"entries": [_entry(id=11), _entry(id=12), _entry(id=13)]},
            2: {"entries": [_entry(id=21)]},
        }
    )
    tool = MinifluxQueryTool(client=http_client)

    result = tool.run({"category_name": "news", "limit": 15})

    assert result.index("[11]") < result.index("[21]") < result.index("[12]") < result.index("[13]")
    params = NEWEST_FIRST | {"limit": 15}
    assert ("/v1/categories/1/entries", params) in http_client.requests
    assert ("/v1/categories/2/entries", params) in http_client.requests


def test_run_reports_the_total_across_categories():
    http_client = _categories_client(
        {
            1: {"entries": [_entry(id=11)], "total": 8},
            2: {"entries": [_entry(id=21)], "total": 10},
        }
    )
    tool = MinifluxQueryTool(client=http_client)

    result = tool.run({"category_name": "news"})

    assert result.splitlines()[0] == "Showing 2 of 18 entries."


def test_run_reports_the_total_for_a_plain_query():
    http_client = FakeHttpClient(
        responses={"/v1/entries": _response({"entries": [_entry()], "total": 112})}
    )
    tool = MinifluxQueryTool(client=http_client)

    assert tool.run({}).splitlines()[0] == "Showing 1 of 112 entries."


def test_run_reports_shown_and_total_counts_for_each_category():
    http_client = _categories_client(
        {
            1: {"entries": [_entry(id=11), _entry(id=12), _entry(id=13)], "total": 8},
            2: {"entries": [_entry(id=21)], "total": 10},
        }
    )
    tool = MinifluxQueryTool(client=http_client)

    result = tool.run({"category_name": "news", "limit": 3})

    assert result.splitlines()[1] == "Categories: News - IT (3 of 8), News - World (1 of 10)"


def test_run_reports_a_category_with_no_entries():
    http_client = _categories_client(
        {1: {"entries": [_entry(id=11)], "total": 8}, 2: {"entries": [], "total": 0}}
    )
    tool = MinifluxQueryTool(client=http_client)

    assert "News - World (0 of 0)" in tool.run({"category_name": "news"})


def test_run_keeps_the_category_counts_when_no_category_has_entries():
    http_client = _categories_client({1: {"entries": []}, 2: {"entries": []}})
    tool = MinifluxQueryTool(client=http_client)

    assert tool.run({"category_name": "news"}).splitlines() == [
        "No entries found.",
        "Categories: News - IT (0 of 0), News - World (0 of 0)",
    ]


def test_run_passes_the_offset_to_each_category():
    http_client = _categories_client({1: {"entries": []}, 2: {"entries": []}})
    tool = MinifluxQueryTool(client=http_client)

    tool.run({"category_name": "news", "limit": 15, "offset": 15})

    params = NEWEST_FIRST | {"limit": 15, "offset": 15}
    assert ("/v1/categories/1/entries", params) in http_client.requests
    assert ("/v1/categories/2/entries", params) in http_client.requests


def test_run_states_the_next_offset_when_a_category_has_more_entries():
    http_client = _categories_client(
        {
            1: {"entries": [_entry(id=11)], "total": 8},
            2: {"entries": [_entry(id=21)], "total": 1},
        }
    )
    tool = MinifluxQueryTool(client=http_client)

    result = tool.run({"category_name": "news", "limit": 1})

    assert result.splitlines()[-1] == "More entries available: call again with offset=1."


def test_run_counts_the_offset_when_stating_the_next_offset():
    http_client = FakeHttpClient(
        responses={"/v1/entries": _response({"entries": [_entry()], "total": 30})}
    )
    tool = MinifluxQueryTool(client=http_client)

    result = tool.run({"limit": 1, "offset": 15})

    assert result.splitlines()[-1] == "More entries available: call again with offset=16."


def test_run_omits_the_next_offset_on_the_last_page():
    http_client = FakeHttpClient(
        responses={"/v1/entries": _response({"entries": [_entry()], "total": 16})}
    )
    tool = MinifluxQueryTool(client=http_client)

    assert "offset=" not in tool.run({"limit": 1, "offset": 15})


def test_run_reports_cumulative_counts_on_later_pages():
    http_client = _categories_client(
        {
            1: {"entries": [_entry(id=n) for n in range(30, 45)], "total": 41},
            2: {"entries": [_entry(id=n) for n in range(50, 55)], "total": 20},
        }
    )
    tool = MinifluxQueryTool(client=http_client)

    lines = tool.run({"category_name": "news", "limit": 15, "offset": 15}).splitlines()

    assert lines[0] == "Showing 50 of 61 entries."
    assert lines[1] == "Categories: News - IT (30 of 41), News - World (20 of 20)"


def test_run_does_not_report_more_than_the_total_past_the_last_page():
    http_client = _categories_client({1: {"entries": [], "total": 5}, 2: {"entries": []}})
    tool = MinifluxQueryTool(client=http_client)

    result = tool.run({"category_name": "news", "offset": 15})

    assert result.splitlines()[1] == "Categories: News - IT (5 of 5), News - World (0 of 0)"


def test_run_hides_entries_with_the_same_title_and_keeps_the_first():
    http_client = FakeHttpClient(
        responses={
            "/v1/entries": _response(
                {
                    "entries": [
                        _entry(id=2, title="Same Story"),
                        _entry(id=3, title="Other Story"),
                        _entry(id=4, title="  same story "),
                    ]
                }
            )
        }
    )
    tool = MinifluxQueryTool(client=http_client)

    result = tool.run({})

    assert "[2]" in result
    assert "[4]" not in result
    assert "Duplicate titles hidden: 1." in result.splitlines()


def test_run_hides_the_same_title_across_categories():
    http_client = _categories_client(
        {
            1: {"entries": [_entry(id=11, title="Same Story")]},
            2: {"entries": [_entry(id=21, title="same story")]},
        }
    )
    tool = MinifluxQueryTool(client=http_client)

    result = tool.run({"category_name": "news"})

    assert "[11]" in result
    assert "[21]" not in result


def test_run_omits_the_duplicate_line_when_titles_are_unique():
    http_client = FakeHttpClient(responses={"/v1/entries": _response({"entries": [_entry()]})})
    tool = MinifluxQueryTool(client=http_client)

    assert "Duplicate" not in tool.run({})


def test_run_rejects_category_name_together_with_feed_name():
    tool = MinifluxQueryTool(client=FakeHttpClient(responses={}))

    with pytest.raises(ValueError, match="either"):
        tool.run({"category_name": "news", "feed_name": "hacker"})


def test_run_shows_the_category_of_each_entry():
    http_client = FakeHttpClient(
        responses={"/v1/entries": _response({"entries": [_entry(category="News - IT")]})}
    )
    tool = MinifluxQueryTool(client=http_client)

    assert "News - IT" in tool.run({})


def test_list_categories_satisfies_tool_port():
    assert isinstance(MinifluxListCategoriesTool(client=FakeHttpClient(responses={})), Tool)


def test_list_categories_shows_names_and_unread_counts():
    http_client = FakeHttpClient(
        responses={
            "/v1/categories": _response(
                [
                    {"id": 3, "title": "News - IT", "total_unread": 730},
                    {"id": 13, "title": "Tech - AI", "total_unread": 1048},
                ]
            )
        }
    )
    tool = MinifluxListCategoriesTool(client=http_client)

    result = tool.run({})

    assert http_client.requests == [("/v1/categories", {"counts": "true"})]
    assert result == "- News - IT (730 unread)\n- Tech - AI (1048 unread)"


def test_list_categories_points_to_the_count_tool_for_date_ranges():
    assert MinifluxCountEntriesByCategoryTool.name in MinifluxListCategoriesTool.description


def _counting_client() -> FakeHttpClient:
    return FakeHttpClient(
        responses={
            "/v1/categories": _response(
                [
                    {"id": 1, "title": "News - MiddleEast"},
                    {"id": 2, "title": "News - World"},
                    {"id": 3, "title": "Tech - AI"},
                ]
            ),
            "/v1/categories/1/entries": _response({"total": 58, "entries": [_entry()]}),
            "/v1/categories/2/entries": _response({"total": 24, "entries": [_entry()]}),
            "/v1/categories/3/entries": _response({"total": 7, "entries": [_entry()]}),
        }
    )


def test_count_entries_by_category_satisfies_the_tool_protocol():
    tool = MinifluxCountEntriesByCategoryTool(client=FakeHttpClient(responses={}))

    assert isinstance(tool, Tool)


def test_count_entries_by_category_requires_category_names():
    schema = MinifluxCountEntriesByCategoryTool.parameters_schema

    assert schema["required"] == ["category_names"]
    assert schema["properties"]["category_names"]["type"] == "array"


def test_count_entries_by_category_reports_only_the_given_categories():
    http_client = _counting_client()
    tool = MinifluxCountEntriesByCategoryTool(client=http_client)

    result = tool.run({"category_names": ["News - MiddleEast", "Tech - AI"]})

    assert result == "- News - MiddleEast: 58 entries\n- Tech - AI: 7 entries\nTotal: 65 entries"
    assert [path for path, _ in http_client.requests] == [
        "/v1/categories",
        "/v1/categories/1/entries",
        "/v1/categories/3/entries",
    ]


def test_count_entries_by_category_requests_one_entry_within_the_date_range():
    http_client = _counting_client()
    tool = MinifluxCountEntriesByCategoryTool(client=http_client)

    tool.run(
        {
            "category_names": ["Tech - AI"],
            "published_after": "2026-11-02T00:00:00+08:00",
            "published_before": "2026-11-03T00:00:00+08:00",
        }
    )

    assert http_client.requests[-1][1] == {
        "limit": 1,
        "published_after": int(datetime(2026, 11, 1, 16, tzinfo=UTC).timestamp()),
        "published_before": int(datetime(2026, 11, 2, 16, tzinfo=UTC).timestamp()),
    }


def test_count_entries_by_category_filters_by_status():
    http_client = _counting_client()
    tool = MinifluxCountEntriesByCategoryTool(client=http_client)

    tool.run({"category_names": ["Tech - AI"], "status": "unread"})

    assert http_client.requests[-1][1] == {"limit": 1, "status": "unread"}


def test_count_entries_by_category_expands_a_shared_prefix():
    tool = MinifluxCountEntriesByCategoryTool(client=_counting_client())

    result = tool.run({"category_names": ["news"]})

    assert result == (
        "- News - MiddleEast: 58 entries\n- News - World: 24 entries\nTotal: 82 entries"
    )


def test_count_entries_by_category_counts_overlapping_names_once():
    tool = MinifluxCountEntriesByCategoryTool(client=_counting_client())

    result = tool.run({"category_names": ["News", "News - World"]})

    assert result.endswith("Total: 82 entries")


def test_count_entries_by_category_rejects_an_unknown_name():
    tool = MinifluxCountEntriesByCategoryTool(client=_counting_client())

    with pytest.raises(ValueError, match="No category starts with 'Sports'"):
        tool.run({"category_names": ["Sports"]})


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
