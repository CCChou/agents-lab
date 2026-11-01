from datetime import datetime

from agent.adapters.current_time import CurrentTimeTool
from agent.adapters.miniflux import MinifluxGetEntryTool, MinifluxQueryTool
from agent.adapters.web import FetchPageTool
from agent.agents.rss import build_rss_spec
from agent.use_cases.summarize_entry import SummarizeEntryTool
from agent.use_cases.tool_registry import ToolRegistry


def test_rss_spec_can_resolve_its_tools():
    tools = [
        MinifluxQueryTool(client=None),
        MinifluxGetEntryTool(client=None),
        FetchPageTool(client=None),
        SummarizeEntryTool(reader=None, llm_client=None),
        CurrentTimeTool(clock=datetime.now),
    ]

    assert ToolRegistry(tools).get(build_rss_spec().tools) == tools


def test_rss_spec_has_a_default_system_prompt():
    assert build_rss_spec().system_prompt


def test_system_prompt_override_replaces_the_default():
    assert build_rss_spec("Be terse.").system_prompt == "Be terse."
