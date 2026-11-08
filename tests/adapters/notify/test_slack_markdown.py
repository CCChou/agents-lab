from agent.adapters.notify.slack_markdown import to_mrkdwn


def test_headings_become_bold_lines():
    assert to_mrkdwn("## 查詢範圍\n### 小節") == "*查詢範圍*\n*小節*"


def test_bold_and_italic_use_slack_markers():
    assert to_mrkdwn("**重要** 和 *強調*") == "*重要* 和 _強調_"


def test_links_use_slack_link_syntax():
    assert to_mrkdwn("[標題](https://example.com/a?x=1)") == "<https://example.com/a?x=1|標題>"


def test_list_markers_become_bullets_and_numbered_lists_stay():
    assert to_mrkdwn("- 一\n* 二\n  - 三\n1. 第一") == "• 一\n• 二\n  • 三\n1. 第一"


def test_special_characters_are_escaped_outside_links():
    assert to_mrkdwn("A & B <C>") == "A &amp; B &lt;C&gt;"


def test_tables_become_one_bullet_per_row():
    table = (
        "| 議題 | 重要度 | 依據文章 |\n"
        "| --- | --- | --- |\n"
        "| AI 晶片 | 高 | [A](https://a.example) |\n"
        "| 選舉 | 中 |  |"
    )

    assert to_mrkdwn(table) == (
        "• *AI 晶片*｜重要度：高｜依據文章：<https://a.example|A>\n• *選舉*｜重要度：中"
    )


def test_code_blocks_are_kept_as_is():
    text = "```\n**not bold** <tag>\n```"

    assert to_mrkdwn(text) == text


def test_inline_code_is_kept_as_is():
    assert to_mrkdwn("執行 `**x**` 指令") == "執行 `**x**` 指令"


def test_paragraphs_and_blank_lines_are_preserved():
    assert to_mrkdwn("第一段\n\n第二段") == "第一段\n\n第二段"
