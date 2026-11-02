from datetime import datetime

from agent.adapters.current_time import CurrentTimeTool
from agent.adapters.miniflux import (
    MinifluxCountEntriesByCategoryTool,
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
        MinifluxCountEntriesByCategoryTool(client=None),
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


def test_default_system_prompt_fixes_the_verification_labels():
    assert "查證欄只能寫已讀內容、部分已讀或僅標題" in build_rss_spec().system_prompt


def test_default_system_prompt_finishes_querying_before_summarizing():
    assert "查詢完成後才能呼叫 summarize_entry" in build_rss_spec().system_prompt


def test_default_system_prompt_avoids_bold_text():
    assert "回覆不要使用粗體" in build_rss_spec().system_prompt


def test_default_system_prompt_prefers_categories_for_topics():
    prompt = build_rss_spec().system_prompt

    assert "miniflux_list_categories" in prompt
    assert "沒有才用 search" in prompt


def test_default_system_prompt_defines_the_remaining_count_and_grouping():
    prompt = build_rss_spec().system_prompt

    assert "總數減去已摘要的篇數" in prompt
    assert "以查詢結果標示的 category 為準" in prompt


def test_default_system_prompt_stops_querying_after_the_plan():
    prompt = build_rss_spec().system_prompt

    assert "計畫內的查詢完成後就不要再查，查詢結果提示還有文章時也一樣" in prompt
    assert "使用者之後要求看更多時，重新規劃，用 offset 接續" in prompt
    assert "只有列文章或使用者要求時才列標題" in prompt
    assert "以最後一次查詢的數字為準" in prompt


def test_rss_spec_allows_more_iterations_but_limits_list_queries():
    spec = build_rss_spec()

    assert spec.max_tool_iterations == 10
    assert spec.tool_call_limits[MinifluxQueryTool.name] == 5


def test_default_system_prompt_probes_the_totals_before_planning():
    prompt = build_rss_spec().system_prompt

    assert "用 miniflux_count_entries_by_category 傳入這次要查的 category" in prompt
    assert "用 search 或 feed_name 時略過探查" in prompt
    assert prompt.index("1. 探查") < prompt.index("2. 規劃") < prompt.index("3. 查詢")


def test_default_system_prompt_plans_the_title_budget_before_querying():
    prompt = build_rss_spec().system_prompt

    assert "依總數和相關度，用一行寫出每個 category 的篇數和總數" in prompt
    assert "每個 category 的篇數不超過它的總數" in prompt
    assert "所有查詢顯示的標題加起來最多 60 篇" in prompt
    assert "這是總量，不是每次查詢或每個 category 的篇數" in prompt
    assert "查詢最多 5 次" in prompt
    assert "越相關的 category 分配越多" in prompt
    assert "15" not in prompt


def test_default_system_prompt_runs_all_planned_queries_together():
    prompt = build_rss_spec().system_prompt

    assert "依計畫從 offset 0 開始，決定每次呼叫的 category_name、limit 和 offset" in prompt
    assert "在同一次回覆裡全部呼叫" in prompt


def test_default_system_prompt_separates_total_and_shown_counts():
    prompt = build_rss_spec().system_prompt

    assert "of 前面是顯示數，後面是總數" in prompt
    assert "分開查詢時要加總" in prompt


def test_system_prompt_override_replaces_the_default():
    assert build_rss_spec("Be terse.").system_prompt == "Be terse."
