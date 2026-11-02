from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, tzinfo
from itertools import zip_longest
from typing import Any, ClassVar, Protocol

import httpx

from agent.adapters.article import format_article, html_to_text
from agent.domain.article import Article

MAX_LIMIT = 20
MIN_STORED_CHARS = 1000


class _HttpClient(Protocol):
    def get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response: ...


def _format_published_at(published_at: str, tz: tzinfo | None) -> str:
    return datetime.fromisoformat(published_at).astimezone(tz).isoformat(timespec="seconds")


def _interleave(pages: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [entry for turn in zip_longest(*pages) for entry in turn if entry is not None]


def _load_article(client: _HttpClient, entry_id: int, tz: tzinfo | None) -> Article:
    response = client.get(f"/v1/entries/{entry_id}")
    response.raise_for_status()
    entry = response.json()
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
        "each matched category. Then lists each article's id, title, feed, category, read "
        "status, published time and URL, without the article text. Titles are usually enough for "
        "overviews and trends. Results are sorted newest first; when several categories match, "
        "results take turns between them, so the combined list is not strictly by time."
    )
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["unread", "read", "removed"],
                "description": "Only return entries with this read status. Omit for all statuses.",
            },
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
            "published_after": {
                "type": "string",
                "description": (
                    "ISO 8601 datetime in the UTC offset from get_current_time; only return "
                    "entries published after this time. For example, if get_current_time "
                    "says 2026-08-20T15:00:00+08:00, today starts at 2026-08-20T00:00:00+08:00."
                ),
            },
            "published_before": {
                "type": "string",
                "description": (
                    "ISO 8601 datetime in the UTC offset from get_current_time; only return "
                    "entries published before this time."
                ),
            },
            "limit": {
                "type": "integer",
                "description": (
                    f"Maximum number of entries to return (default 10, max {MAX_LIMIT}). "
                    "When several categories match, this limits the combined list."
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
        page = self._get_page(path, params)
        return self._format_entries(page["entries"], page["total"])

    def _query_categories(self, category_name: str, params: dict[str, Any]) -> str:
        categories = self._resolve_categories(category_name)
        pages = [
            self._get_page(f"/v1/categories/{category['id']}/entries", params)
            for category in categories
        ]
        entries = _interleave([page["entries"] for page in pages])[: params["limit"]]
        shown_ids = {entry["id"] for entry in entries}
        counts = ", ".join(
            f"{category['title']} "
            f"({sum(entry['id'] in shown_ids for entry in page['entries'])} of {page['total']})"
            for category, page in zip(categories, pages, strict=True)
        )
        total = sum(page["total"] for page in pages)
        return self._format_entries(entries, total, scope=f"Categories: {counts}")

    def _get_page(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def _build_params(self, arguments: dict[str, Any]) -> dict[str, Any]:
        params: dict[str, Any] = {
            "limit": min(arguments.get("limit", 10), MAX_LIMIT),
            "order": "published_at",
            "direction": "desc",
        }
        for key in ("status", "search"):
            if key in arguments:
                params[key] = arguments[key]
        for key in ("published_after", "published_before"):
            if key in arguments:
                params[key] = self._to_unix_timestamp(arguments[key])
        return params

    @staticmethod
    def _to_unix_timestamp(iso_datetime: str) -> int:
        return int(datetime.fromisoformat(iso_datetime).timestamp())

    def _resolve_categories(self, category_name: str) -> list[dict[str, Any]]:
        response = self._client.get("/v1/categories")
        response.raise_for_status()
        prefix = category_name.lower()
        categories = [
            category for category in response.json() if category["title"].lower().startswith(prefix)
        ]
        if not categories:
            raise ValueError(
                f"No category starts with '{category_name}'. "
                "Use miniflux_list_categories to see the available categories."
            )
        return categories

    def _resolve_feed_id(self, feed_name: str) -> int:
        response = self._client.get("/v1/feeds")
        response.raise_for_status()
        for feed in response.json():
            if feed_name.lower() in feed["title"].lower():
                return feed["id"]
        raise ValueError(f"No feed found matching '{feed_name}'")

    def _format_entries(
        self, entries: list[dict[str, Any]], total: int, scope: str | None = None
    ) -> str:
        lines = [f"Showing {len(entries)} of {total} entries." if entries else "No entries found."]
        if scope:
            lines.append(scope)
        lines += [
            f"- [{entry['id']}] {entry['title']} "
            f"({entry['feed']['title']}, {entry['feed']['category']['title']}, {entry['status']}, "
            f"{_format_published_at(entry['published_at'], self._tz)}) {entry['url']}"
            for entry in entries
        ]
        return "\n".join(lines)


class MinifluxListCategoriesTool:
    name = "miniflux_list_categories"
    description = (
        "List the category titles in the user's Miniflux RSS reader with their unread counts. "
        "Use this to find the title or shared prefix for category_name."
    )
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    def __init__(self, *, client: _HttpClient) -> None:
        self._client = client

    def run(self, arguments: dict[str, Any]) -> str:
        response = self._client.get("/v1/categories", params={"counts": "true"})
        response.raise_for_status()
        categories = response.json()
        if not categories:
            return "No categories found."
        return "\n".join(
            f"- {category['title']} ({category['total_unread']} unread)" for category in categories
        )


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
