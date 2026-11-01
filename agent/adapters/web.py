import ipaddress
import socket
from collections.abc import Callable
from typing import Any, ClassVar
from urllib.parse import urljoin, urlsplit

import httpx

from agent.adapters.article import format_article, html_to_text

MAX_BYTES = 2_000_000
MAX_REDIRECTS = 5


def _resolve(host: str) -> list[str]:
    try:
        return [info[4][0] for info in socket.getaddrinfo(host, None)]
    except socket.gaierror:
        return []


class FetchPageTool:
    name = "fetch_page"
    description = (
        "Read the text of a public web page by URL. Use this when an article's stored "
        "content is missing or only a short excerpt. Long pages are returned in parts."
    )
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The http or https URL to read."},
            "offset": {
                "type": "integer",
                "description": "Character offset to continue reading from (default 0).",
            },
        },
        "required": ["url"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        *,
        client: httpx.Client,
        resolve: Callable[[str], list[str]] = _resolve,
    ) -> None:
        self._client = client
        self._resolve = resolve

    def run(self, arguments: dict[str, Any]) -> str:
        url, text = self._read(arguments["url"])
        return format_article(f"URL: {url}", text, arguments.get("offset", 0))

    def read_text(self, url: str) -> str:
        return self._read(url)[1]

    def _read(self, start_url: str) -> tuple[str, str]:
        url = start_url
        for _ in range(MAX_REDIRECTS + 1):
            self._check_url(url)
            with self._client.stream("GET", url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["location"])
                    continue
                response.raise_for_status()
                self._check_content_type(response)
                return url, html_to_text(self._read_body(response), response.charset_encoding)
        raise ValueError(f"Too many redirects from {start_url}")

    def _check_url(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise ValueError(f"Only http and https URLs can be read: {url}")
        addresses = self._resolve(parts.hostname) if parts.hostname else []
        if not addresses or not all(ipaddress.ip_address(a).is_global for a in addresses):
            raise ValueError(f"Refusing to read {parts.hostname}: not a public address")

    @staticmethod
    def _check_content_type(response: httpx.Response) -> None:
        content_type = response.headers.get("content-type", "text/html")
        if not content_type.startswith(("text/", "application/xhtml")):
            raise ValueError(f"Cannot read content of type {content_type}")

    @staticmethod
    def _read_body(response: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_bytes():
            chunks.append(chunk)
            size += len(chunk)
            if size >= MAX_BYTES:
                break
        return b"".join(chunks)[:MAX_BYTES]
