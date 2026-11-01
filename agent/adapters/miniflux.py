from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, tzinfo
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
        "Query articles from the user's Miniflux RSS reader. Supports filtering by "
        "read status, feed name, a search keyword, and a published date range. "
        "Results are sorted newest first and do not include the article text."
    )
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["unread", "read", "removed"],
                "description": "Only return entries with this read status.",
            },
            "feed_name": {
                "type": "string",
                "description": (
                    "Only return entries from the feed whose title contains this text "
                    "(case-insensitive)."
                ),
            },
            "search": {
                "type": "string",
                "description": "Only return entries whose title or content match this keyword.",
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
                "description": f"Maximum number of entries to return (default 10, max {MAX_LIMIT}).",
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, *, client: _HttpClient, tz: tzinfo | None = None) -> None:
        self._client = client
        self._tz = tz

    def run(self, arguments: dict[str, Any]) -> str:
        params = self._build_params(arguments)
        path = "/v1/entries"
        if "feed_name" in arguments:
            feed_id = self._resolve_feed_id(arguments["feed_name"])
            path = f"/v1/feeds/{feed_id}/entries"
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return self._format_entries(response.json()["entries"])

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

    def _resolve_feed_id(self, feed_name: str) -> int:
        response = self._client.get("/v1/feeds")
        response.raise_for_status()
        for feed in response.json():
            if feed_name.lower() in feed["title"].lower():
                return feed["id"]
        raise ValueError(f"No feed found matching '{feed_name}'")

    def _format_entries(self, entries: list[dict[str, Any]]) -> str:
        if not entries:
            return "No entries found."
        return "\n".join(
            f"- [{entry['id']}] {entry['title']} "
            f"({entry['feed']['title']}, {entry['status']}, "
            f"{_format_published_at(entry['published_at'], self._tz)}) {entry['url']}"
            for entry in entries
        )


class MinifluxGetEntryTool:
    name = "miniflux_get_entry"
    description = (
        "Read the content stored in Miniflux for one article, by the id shown in "
        "miniflux_query_entries results. Some feeds store only a short excerpt. "
        "Long articles are returned in parts."
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
