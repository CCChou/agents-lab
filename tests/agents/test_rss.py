from datetime import datetime

from agent.adapters.current_time import CurrentTimeTool
from agent.adapters.miniflux import (
    MinifluxGetEntryTool,
    MinifluxListCategoriesTool,
    MinifluxQueryTool,
)
from agent.adapters.web import FetchPageTool
from agent.agents.rss import MAX_SUMMARIES_PER_TURN, build_rss_spec
from agent.use_cases.summarize_entry import SummarizeEntryTool
from agent.use_cases.tool_registry import ToolRegistry


def test_rss_spec_can_resolve_its_tools():
    tools = [
        MinifluxQueryTool(client=None),
        MinifluxListCategoriesTool(client=None),
        MinifluxGetEntryTool(client=None),
        FetchPageTool(client=None),
        SummarizeEntryTool(reader=None, llm_client=None),
        CurrentTimeTool(clock=datetime.now),
    ]

    assert ToolRegistry(tools).get(build_rss_spec().tools) == tools


def test_rss_spec_has_a_default_system_prompt():
    assert build_rss_spec().system_prompt


def test_default_system_prompt_triages_by_title_before_reading_text():
    prompt = build_rss_spec().system_prompt

    assert "只列標題，不要摘要或讀內文" in prompt
    assert "最多 5 篇" in prompt
    assert "重要度" in prompt
    assert "同一次回覆" in prompt
    assert "不要摘要整份清單" in prompt


def test_default_system_prompt_maps_news_and_tech_to_category_prefixes():
    prompt = build_rss_spec().system_prompt

    assert 'category_name="News"' in prompt
    assert 'category_name="Tech"' in prompt


def test_rss_spec_enforces_the_summary_limit_stated_in_the_prompt():
    spec = build_rss_spec()

    assert spec.tool_call_limits == {SummarizeEntryTool.name: MAX_SUMMARIES_PER_TURN}
    assert f"最多 {MAX_SUMMARIES_PER_TURN} 篇" in spec.system_prompt


def test_default_system_prompt_marks_evidence_and_stays_within_stated_facts():
    prompt = build_rss_spec().system_prompt

    assert "已讀內容" in prompt
    assert "僅標題" in prompt
    assert "明確提到的事實" in prompt
    assert "從已摘要的文章中挑選" in prompt


def test_default_system_prompt_defines_the_reply_format():
    prompt = build_rss_spec().system_prompt

    for section in ("## 查詢範圍", "## 議題趨勢", "## 文章摘要", "## 推薦閱讀", "## 其他標題"):
        assert section in prompt


def test_default_system_prompt_separates_article_metadata_from_the_summary():
    assert "來源｜category｜發布時間\n\n摘要內容" in build_rss_spec().system_prompt


def test_default_system_prompt_prefers_categories_for_topics():
    prompt = build_rss_spec().system_prompt

    assert "miniflux_list_categories" in prompt
    assert "沒有才用 search" in prompt


def test_default_system_prompt_defines_the_remaining_count_and_grouping():
    prompt = build_rss_spec().system_prompt

    assert "總數減去已摘要的篇數" in prompt
    assert "以查詢結果標示的 category 為準" in prompt


def test_default_system_prompt_limits_the_entry_list_to_one_query():
    prompt = build_rss_spec().system_prompt

    assert "不要換參數重查" in prompt
    assert "這次查詢已取得的其餘標題" in prompt


def test_system_prompt_override_replaces_the_default():
    assert build_rss_spec("Be terse.").system_prompt == "Be terse."
