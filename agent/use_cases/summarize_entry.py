from typing import Any, ClassVar

from agent.domain.interfaces import ArticleReader, LLMClient
from agent.domain.message import Message
from agent.domain.tool import ToolCall
from agent.domain.untrusted import wrap_untrusted

MAX_INPUT_CHARS = 4000
SYSTEM_PROMPT = (
    "你負責摘要一篇文章。用繁體中文寫出不超過 150 字的重點，只根據文章內容，不要加入其他資訊。"
    "只輸出摘要本身。"
)


class SummarizeEntryTool:
    name = "summarize_entry"
    description = (
        "Summarize one article by the id shown in miniflux_query_entries results. Reads the "
        "full text when needed and returns only a short summary. Each call makes one separate "
        "LLM request, so call this only for articles you have chosen, not for every article "
        "in a list."
    )
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "entry_id": {"type": "integer", "description": "The id of the article to summarize."},
        },
        "required": ["entry_id"],
        "additionalProperties": False,
    }

    def __init__(self, *, reader: ArticleReader, llm_client: LLMClient) -> None:
        self._reader = reader
        self._llm_client = llm_client

    def run(self, arguments: dict[str, Any]) -> str:
        article = self._reader.read(arguments["entry_id"])
        if not article.text:
            raise ValueError(f"Article {arguments['entry_id']} has no readable text")

        messages = [
            Message.from_text("system", SYSTEM_PROMPT),
            Message.from_text("user", wrap_untrusted(article.text[:MAX_INPUT_CHARS])),
        ]
        chunks = self._llm_client.stream(messages, None)
        summary = "".join(chunk for chunk in chunks if not isinstance(chunk, ToolCall))

        parts = [article.metadata, "Summary:", wrap_untrusted(summary)]
        if len(article.text) > MAX_INPUT_CHARS:
            parts.append(
                f"[Summary covers only the first {MAX_INPUT_CHARS} of "
                f"{len(article.text)} characters.]"
            )
        return "\n".join(parts)
