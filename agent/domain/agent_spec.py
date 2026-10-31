from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSpec:
    name: str
    system_prompt: str | None = None
    model: str | None = None
    tools: tuple[str, ...] = ()
    max_tool_iterations: int = 5
