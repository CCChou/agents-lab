from bs4 import BeautifulSoup

from agent.domain.untrusted import wrap_untrusted

MAX_CHARS = 8000

_DROPPED_TAGS = ["head", "script", "style", "noscript", "nav", "aside", "footer", "form", "iframe"]
_BLOCK_TAGS = [
    "p",
    "div",
    "br",
    "li",
    "tr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "pre",
    "blockquote",
]


def html_to_text(html: str | bytes, encoding: str | None = None) -> str:
    soup = BeautifulSoup(html, "html.parser", from_encoding=encoding)
    for tag in soup(_DROPPED_TAGS):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup
    for tag in root.find_all(_BLOCK_TAGS):
        tag.insert_after("\n")
    lines = (" ".join(line.split()) for line in root.get_text().splitlines())
    return "\n".join(line for line in lines if line)


def format_article(metadata: str, text: str, offset: int = 0) -> str:
    start = max(offset, 0)
    end = min(start + MAX_CHARS, len(text))
    chunk = text[start:end]
    if not chunk:
        return f"{metadata}\nNo more content at offset {start} (total {len(text)} characters)."

    parts = [metadata, wrap_untrusted(chunk)]
    if end < len(text):
        parts.append(
            f"[Showing characters {start}-{end} of {len(text)}. "
            f"Call again with offset={end} to continue.]"
        )
    return "\n".join(parts)
