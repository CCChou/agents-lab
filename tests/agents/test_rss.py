from datetime import datetime

from agent.adapters.current_time import CurrentTimeTool
from agent.adapters.miniflux import MinifluxQueryTool
from agent.agents.rss import build_rss_spec
from agent.use_cases.tool_registry import ToolRegistry


def test_rss_spec_can_resolve_its_tools():
    miniflux = MinifluxQueryTool(client=None)
    current_time = CurrentTimeTool(clock=datetime.now)

    assert ToolRegistry([miniflux, current_time]).get(build_rss_spec().tools) == [
        miniflux,
        current_time,
    ]


def test_rss_spec_has_a_default_system_prompt():
    assert build_rss_spec().system_prompt


def test_system_prompt_override_replaces_the_default():
    assert build_rss_spec("Be terse.").system_prompt == "Be terse."
