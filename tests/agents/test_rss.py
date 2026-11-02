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
    assert "預設不讀內文" in prompt
    assert "最多 5 篇" in prompt
    assert "重要度" in prompt
    assert "同一次回覆" in prompt
    assert "不要摘要整份清單" in prompt


def test_default_system_prompt_maps_news_and_tech_to_category_prefixes():
    prompt = build_rss_spec().system_prompt

    assert "新聞、news：News\n" in prompt
    assert "科技、tech：Tech\n" in prompt
    assert "中東、伊朗、以色列、加薩：News - MiddleEast" in prompt
    assert "IT 新聞：Tech - IT News" in prompt
    assert "不要先查 News 或 Tech" in prompt


def test_rss_spec_enforces_the_summary_limit_stated_in_the_prompt():
    spec = build_rss_spec()

    assert spec.tool_call_limits[SummarizeEntryTool.name] == MAX_SUMMARIES_PER_TURN
    assert f"最多 {MAX_SUMMARIES_PER_TURN} 篇" in spec.system_prompt


def test_default_system_prompt_marks_evidence_and_stays_within_stated_facts():
    prompt = build_rss_spec().system_prompt

    assert "已讀內容" in prompt
    assert "僅標題" in prompt
    assert "明確提到的事實" in prompt
    assert "從已摘要的文章中挑選" in prompt


def test_default_system_prompt_defines_the_reply_format():
    prompt = build_rss_spec().system_prompt

    for section in ("## 查詢範圍", "## 議題趨勢", "## 文章摘要", "## 推薦閱讀", "## 文章列表"):
        assert section in prompt


def test_default_system_prompt_separates_article_metadata_from_the_summary():
    assert "來源｜category｜發布時間\n\n摘要內容" in build_rss_spec().system_prompt


def test_default_system_prompt_builds_trends_from_all_titles_before_verifying():
    prompt = build_rss_spec().system_prompt

    assert "先從所有標題依出現次數和影響範圍歸納議題" in prompt
    assert "沒有摘要的議題也要列出" in prompt
    assert "不要把一篇文章當成一個議題" in prompt
    assert "摘要只用來查證最重要的議題" in prompt


def test_default_system_prompt_keeps_the_importance_column_short():
    prompt = build_rss_spec().system_prompt

    assert "重要度欄只寫高、中高、中、低" in prompt
    assert "簡要判讀" in prompt


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

    assert "同一個範圍只查一次" in prompt
    assert "才用 offset 查下一頁" in prompt
    assert "只有列文章或使用者要求時才列標題" in prompt
    assert "其他標題" not in prompt
    assert "以最後一次查詢的數字為準" in prompt


def test_rss_spec_allows_more_iterations_but_limits_list_queries():
    spec = build_rss_spec()

    assert spec.max_tool_iterations == 10
    assert spec.tool_call_limits[MinifluxQueryTool.name] == 5


def test_default_system_prompt_requests_fifteen_titles_per_category():
    assert "limit 用 15" in build_rss_spec().system_prompt


def test_default_system_prompt_queries_selected_categories_separately():
    prompt = build_rss_spec().system_prompt

    assert "用完整名稱分別查詢" in prompt
    assert "在同一次回覆裡一起呼叫" in prompt


def test_default_system_prompt_separates_total_and_shown_counts():
    prompt = build_rss_spec().system_prompt

    assert "of 前面是顯示數，後面是總數" in prompt
    assert "分開查詢時要加總" in prompt


def test_system_prompt_override_replaces_the_default():
    assert build_rss_spec("Be terse.").system_prompt == "Be terse."
