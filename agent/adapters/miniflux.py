from datetime import datetime, tzinfo
from typing import Any, ClassVar, Protocol

import httpx


class _HttpClient(Protocol):
    def get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response: ...


class MinifluxQueryTool:
    name = "miniflux_query_entries"
    description = (
        "Query articles from the user's Miniflux RSS reader. Supports filtering by "
        "read status, feed name, a search keyword, and a published date range."
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
                    "ISO 8601 datetime (e.g. '2026-08-20T00:00:00+00:00'); only return "
                    "entries published after this time."
                ),
            },
            "published_before": {
                "type": "string",
                "description": "ISO 8601 datetime; only return entries published before this time.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of entries to return (default 10).",
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
        params: dict[str, Any] = {"limit": arguments.get("limit", 10)}
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
            f"{self._format_published_at(entry['published_at'])}) {entry['url']}"
            for entry in entries
        )

    def _format_published_at(self, published_at: str) -> str:
        return (
            datetime.fromisoformat(published_at).astimezone(self._tz).isoformat(timespec="seconds")
        )
