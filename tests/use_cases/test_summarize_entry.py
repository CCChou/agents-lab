from collections.abc import Iterator

import pytest

from agent.domain.article import Article
from agent.domain.interfaces import LLMClient
from agent.domain.message import Message
from agent.domain.tool import Tool, ToolCall
from agent.use_cases.summarize_entry import MAX_INPUT_CHARS, SummarizeEntryTool


def article(text: str = "Article body") -> Article:
    return Article(
        title="Some Article",
        feed="Some Feed",
        published_at="2026-11-01T22:00:00+08:00",
        url="https://example.test/1",
        text=text,
    )


class FakeReader:
    def __init__(self, result: Article) -> None:
        self._result = result
        self.requested: list[int] = []

    def read(self, entry_id: int) -> Article:
        self.requested.append(entry_id)
        return self._result


class FakeLLMClient:
    def __init__(self, chunks: list[str | ToolCall] | None = None) -> None:
        self._chunks = chunks if chunks is not None else ["Short ", "summary"]
        self.messages: list[Message] = []
        self.tools: list[Tool] | None = None

    def stream(
        self, messages: list[Message], tools: list[Tool] | None = None
    ) -> Iterator[str | ToolCall]:
        self.messages = messages
        self.tools = tools
        yield from self._chunks


def test_satisfies_tool_port():
    tool = SummarizeEntryTool(reader=FakeReader(article()), llm_client=FakeLLMClient())

    assert isinstance(tool, Tool)


def test_fake_satisfies_llm_client_port():
    assert isinstance(FakeLLMClient(), LLMClient)


def test_run_reads_the_requested_entry():
    reader = FakeReader(article())

    SummarizeEntryTool(reader=reader, llm_client=FakeLLMClient()).run({"entry_id": 7})

    assert reader.requested == [7]


def test_run_sends_only_this_article_as_untrusted_content_without_tools():
    llm_client = FakeLLMClient()

    SummarizeEntryTool(reader=FakeReader(article()), llm_client=llm_client).run({"entry_id": 1})

    system, user = llm_client.messages
    assert system.role == "system"
    assert user.role == "user"
    assert "<untrusted_content>\nArticle body\n</untrusted_content>" in user.text
    assert llm_client.tools is None


def test_run_returns_metadata_and_the_joined_summary():
    tool = SummarizeEntryTool(reader=FakeReader(article()), llm_client=FakeLLMClient())

    result = tool.run({"entry_id": 1})

    assert "Title: Some Article" in result
    assert "URL: https://example.test/1" in result
    assert "<untrusted_content>\nShort summary\n</untrusted_content>" in result


def test_run_does_not_return_the_article_text():
    tool = SummarizeEntryTool(reader=FakeReader(article()), llm_client=FakeLLMClient())

    assert "Article body" not in tool.run({"entry_id": 1})


def test_run_limits_the_input_and_says_the_summary_is_partial():
    text = "a" * (MAX_INPUT_CHARS + 5)
    llm_client = FakeLLMClient()
    tool = SummarizeEntryTool(reader=FakeReader(article(text)), llm_client=llm_client)

    result = tool.run({"entry_id": 1})

    assert "a" * MAX_INPUT_CHARS in llm_client.messages[1].text
    assert "a" * (MAX_INPUT_CHARS + 1) not in llm_client.messages[1].text
    assert f"first {MAX_INPUT_CHARS} of {MAX_INPUT_CHARS + 5}" in result


def test_run_does_not_mention_truncation_for_short_articles():
    tool = SummarizeEntryTool(reader=FakeReader(article()), llm_client=FakeLLMClient())

    assert "first" not in tool.run({"entry_id": 1})


def test_run_raises_when_the_article_has_no_text():
    llm_client = FakeLLMClient()
    tool = SummarizeEntryTool(reader=FakeReader(article("")), llm_client=llm_client)

    with pytest.raises(ValueError, match="no readable text"):
        tool.run({"entry_id": 1})

    assert llm_client.messages == []
