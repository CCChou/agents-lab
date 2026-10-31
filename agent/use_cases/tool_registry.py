from collections.abc import Iterable

from agent.domain.tool import Tool


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def get(self, names: Iterable[str]) -> list[Tool]:
        return [self._lookup(name) for name in names]

    def _lookup(self, name: str) -> Tool:
        if name not in self._tools:
            raise ValueError(f"Unknown tool '{name}'")
        return self._tools[name]
