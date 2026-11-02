from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, tzinfo
from itertools import zip_longest
from typing import Any, ClassVar, Protocol

import httpx

from agent.adapters.article import format_article, html_to_text
from agent.domain.article import Article

MAX_LIMIT = 15
MIN_STORED_CHARS = 1000

_STATUS_PROPERTY: dict[str, Any] = {
    "type": "string",
    "enum": ["unread", "read", "removed"],
    "description": "Only include entries with this read status. Omit for all statuses.",
}
_DATE_RANGE_PROPERTIES: dict[str, Any] = {
    "published_after": {
        "type": "string",
        "description": (
            "ISO 8601 datetime in the UTC offset from get_current_time; only include "
            "entries published after this time. For example, if get_current_time "
            "says 2026-08-20T15:00:00+08:00, today starts at 2026-08-20T00:00:00+08:00."
        ),
    },
    "published_before": {
        "type": "string",
        "description": (
            "ISO 8601 datetime in the UTC offset from get_current_time; only include "
            "entries published before this time."
        ),
    },
}


class _HttpClient(Protocol):
    def get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response: ...


def _format_published_at(published_at: str, tz: tzinfo | None) -> str:
    return datetime.fromisoformat(published_at).astimezone(tz).isoformat(timespec="seconds")


def _interleave(pages: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [entry for turn in zip_longest(*pages) for entry in turn if entry is not None]


def _drop_duplicate_titles(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for entry in entries:
        unique.setdefault(entry["title"].strip().lower(), entry)
    return list(unique.values())


def _get_json(client: _HttpClient, path: str, params: dict[str, Any] | None = None) -> Any:
    response = client.get(path, params=params)
    response.raise_for_status()
    return response.json()


def _date_params(arguments: dict[str, Any]) -> dict[str, int]:
    return {
        key: int(datetime.fromisoformat(arguments[key]).timestamp())
        for key in _DATE_RANGE_PROPERTIES
        if key in arguments
    }


def _match_categories(categories: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    prefix = name.lower()
    matched = [category for category in categories if category["title"].lower().startswith(prefix)]
    if not matched:
        raise ValueError(
            f"No category starts with '{name}'. "
            "Use miniflux_list_categories to see the available categories."
        )
    return matched


def _load_article(client: _HttpClient, entry_id: int, tz: tzinfo | None) -> Article:
    entry = _get_json(client, f"/v1/entries/{entry_id}")
    return Article(
        title=entry["title"],
        feed=entry["feed"]["title"],
        published_at=_format_published_at(entry["published_at"], tz),
        url=entry["url"],
        text=html_to_text(entry["content"]),
    )


class MinifluxQueryTool:
    name = "miniflux_query_entries"
    description = (
        "Query articles from the user's Miniflux RSS reader. Supports filtering by read status, "
        "category, feed name, a search keyword, and a published date range. Starts with the total "
        "number of matching articles, and with category_name also the shown and total counts of "
        "each matched category; shown counts include earlier pages. Articles with the same title "
        "are listed once. Then lists each article's id, title, feed, category, read "
        "status, published time and URL, without the article text. Titles are usually enough for "
        "overviews and trends. Results are sorted newest first; when several categories match, "
        "results take turns between them, so the combined list is not strictly by time."
    )
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "status": _STATUS_PROPERTY,
            "category_name": {
                "type": "string",
                "description": (
                    "Use this when the user asks about a topic that a category covers. Only "
                    "return entries from every category whose title starts with this text "
                    "(case-insensitive), so a shared prefix covers a group of categories. Use "
                    "miniflux_list_categories to see the titles. Cannot be used with feed_name."
                ),
            },
            "feed_name": {
                "type": "string",
                "description": (
                    "Only return entries from the first feed whose title contains this text "
                    "(case-insensitive). Cannot be used with category_name."
                ),
            },
            "search": {
                "type": "string",
                "description": (
                    "Only return entries whose title or content match this keyword. Broad words "
                    "can match unrelated articles, so prefer category_name for broad topics."
                ),
            },
            **_DATE_RANGE_PROPERTIES,
            "limit": {
                "type": "integer",
                "description": (
                    f"Maximum number of entries to return (default 10, max {MAX_LIMIT}). "
                    f"Larger values are reduced to {MAX_LIMIT} to keep responses small; "
                    "use offset to read more. With category_name, this applies to each "
                    "matched category."
                ),
            },
            "offset": {
                "type": "integer",
                "description": (
                    "Number of entries to skip, to read the next page (default 0). Results state "
                    "the next offset when more entries are available. With category_name, this "
                    "applies to each matched category."
                ),
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, *, client: _HttpClient, tz: tzinfo | None = None) -> None:
        self._client = client
        self._tz = tz

    def run(self, arguments: dict[str, Any]) -> str:
        if "category_name" in arguments and "feed_name" in arguments:
            raise ValueError("Use either category_name or feed_name, not both")

        params = self._build_params(arguments)
        if "category_name" in arguments:
            return self._query_categories(arguments["category_name"], params)

        path = "/v1/entries"
        if "feed_name" in arguments:
            path = f"/v1/feeds/{self._resolve_feed_id(arguments['feed_name'])}/entries"
        return self._format_result([_get_json(self._client, path, params)], params)

    def _query_categories(self, category_name: str, params: dict[str, Any]) -> str:
        categories = _match_categories(_get_json(self._client, "/v1/categories"), category_name)
        pages = [
            _get_json(self._client, f"/v1/categories/{category['id']}/entries", params)
            for category in categories
        ]
        return self._format_result(pages, params, [category["title"] for category in categories])

    def _build_params(self, arguments: dict[str, Any]) -> dict[str, Any]:
        params: dict[str, Any] = {
            "limit": min(arguments.get("limit", 10), MAX_LIMIT),
            "order": "published_at",
            "direction": "desc",
        }
        for key in ("status", "search", "offset"):
            if key in arguments:
                params[key] = arguments[key]
        return params | _date_params(arguments)

    def _resolve_feed_id(self, feed_name: str) -> int:
        for feed in _get_json(self._client, "/v1/feeds"):
            if feed_name.lower() in feed["title"].lower():
                return feed["id"]
        raise ValueError(f"No feed found matching '{feed_name}'")

    def _format_result(
        self,
        pages: list[dict[str, Any]],
        params: dict[str, Any],
        category_titles: list[str] | None = None,
    ) -> str:
        offset = params.get("offset", 0)
        shown = [min(offset + len(page["entries"]), page["total"]) for page in pages]
        totals = [page["total"] for page in pages]
        fetched = _interleave([page["entries"] for page in pages])
        entries = _drop_duplicate_titles(fetched)

        lines = [
            f"Showing {sum(shown)} of {sum(totals)} entries." if entries else "No entries found."
        ]
        if category_titles:
            counts = ", ".join(
                f"{title} ({count} of {total})"
                for title, count, total in zip(category_titles, shown, totals, strict=True)
            )
            lines.append(f"Categories: {counts}")
        if len(entries) < len(fetched):
            lines.append(f"Duplicate titles hidden: {len(fetched) - len(entries)}.")
        lines += [
            f"- [{entry['id']}] {entry['title']} "
            f"({entry['feed']['title']}, {entry['feed']['category']['title']}, {entry['status']}, "
            f"{_format_published_at(entry['published_at'], self._tz)}) {entry['url']}"
            for entry in entries
        ]
        if any(count < total for count, total in zip(shown, totals, strict=True)):
            next_offset = offset + params["limit"]
            lines.append(f"More entries available: call again with offset={next_offset}.")
        return "\n".join(lines)


class MinifluxListCategoriesTool:
    name = "miniflux_list_categories"
    description = (
        "List the category titles in the user's Miniflux RSS reader with their unread counts. "
        "Use this to find the title or shared prefix for category_name. Unread counts ignore "
        "dates; use miniflux_count_entries_by_category to count articles in a date range."
    )
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    def __init__(self, *, client: _HttpClient) -> None:
        self._client = client

    def run(self, arguments: dict[str, Any]) -> str:
        categories = _get_json(self._client, "/v1/categories", {"counts": "true"})
        if not categories:
            return "No categories found."
        return "\n".join(
            f"- {category['title']} ({category['total_unread']} unread)" for category in categories
        )


class MinifluxCountEntriesByCategoryTool:
    name = "miniflux_count_entries_by_category"
    description = (
        "Count the articles in the given Miniflux categories, optionally by read status and "
        "published date range, without listing them. Use this before miniflux_query_entries to decide "
        "how many articles to read from each category."
    )
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "category_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Category titles to count. A shared prefix covers a group of categories "
                    "(case-insensitive). Only pass the categories you need."
                ),
            },
            "status": _STATUS_PROPERTY,
            **_DATE_RANGE_PROPERTIES,
        },
        "required": ["category_names"],
        "additionalProperties": False,
    }

    def __init__(self, *, client: _HttpClient) -> None:
        self._client = client

    def run(self, arguments: dict[str, Any]) -> str:
        params: dict[str, Any] = {"limit": 1} | _date_params(arguments)
        if "status" in arguments:
            params["status"] = arguments["status"]

        categories = _get_json(self._client, "/v1/categories")
        matched = {
            category["id"]: category["title"]
            for name in arguments["category_names"]
            for category in _match_categories(categories, name)
        }
        totals = {
            title: _get_json(self._client, f"/v1/categories/{category_id}/entries", params)["total"]
            for category_id, title in matched.items()
        }
        lines = [f"- {title}: {total} entries" for title, total in totals.items()]
        lines.append(f"Total: {sum(totals.values())} entries")
        return "\n".join(lines)


class MinifluxGetEntryTool:
    name = "miniflux_get_entry"
    description = (
        "Read the content stored in Miniflux for one article in detail, by the id shown in "
        "miniflux_query_entries results. Some feeds store only a short excerpt. "
        "Long articles are returned in parts, and each part states the next offset."
    )
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "entry_id": {"type": "integer", "description": "The id of the article to read."},
            "offset": {
                "type": "integer",
                "description": "Character offset to continue reading from (default 0).",
            },
        },
        "required": ["entry_id"],
        "additionalProperties": False,
    }

    def __init__(self, *, client: _HttpClient, tz: tzinfo | None = None) -> None:
        self._client = client
        self._tz = tz

    def run(self, arguments: dict[str, Any]) -> str:
        article = _load_article(self._client, arguments["entry_id"], self._tz)
        return format_article(article.metadata, article.text, arguments.get("offset", 0))


class MinifluxArticleReader:
    def __init__(
        self,
        *,
        client: _HttpClient,
        read_page: Callable[[str], str],
        tz: tzinfo | None = None,
    ) -> None:
        self._client = client
        self._read_page = read_page
        self._tz = tz

    def read(self, entry_id: int) -> Article:
        article = _load_article(self._client, entry_id, self._tz)
        if len(article.text) >= MIN_STORED_CHARS:
            return article
        try:
            page_text = self._read_page(article.url)
        except (httpx.HTTPError, ValueError):
            return article
        return replace(article, text=page_text) if len(page_text) > len(article.text) else article
