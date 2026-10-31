from typing import Any, ClassVar

import pytest

from agent.use_cases.tool_registry import ToolRegistry


class FakeTool:
    description = "a fake tool"
    parameters_schema: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, arguments: dict[str, Any]) -> str:
        return "result"


def test_get_returns_the_named_tools_in_the_requested_order():
    lookup, search = FakeTool("lookup"), FakeTool("search")
    registry = ToolRegistry([lookup, search])

    assert registry.get(["search", "lookup"]) == [search, lookup]


def test_get_leaves_out_tools_that_were_not_requested():
    lookup = FakeTool("lookup")
    registry = ToolRegistry([lookup, FakeTool("search")])

    assert registry.get(["lookup"]) == [lookup]


def test_get_raises_for_an_unknown_tool_name():
    registry = ToolRegistry([])

    with pytest.raises(ValueError, match="missing"):
        registry.get(["missing"])
