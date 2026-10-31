import logging
import os
import sys
from collections.abc import Iterator

import httpx

from agent.adapters.cli import run
from agent.adapters.in_memory_store import InMemoryConversationStore
from agent.adapters.miniflux import MinifluxQueryTool
from agent.adapters.openai_compatible import OpenAICompatibleLLMClient
from agent.agents.rss import build_rss_spec
from agent.config import LLMConfig, MinifluxConfig
from agent.domain.tool import Tool
from agent.use_cases.context_builder import ContextBuilder
from agent.use_cases.loop_agent import LoopAgent
from agent.use_cases.tool_registry import ToolRegistry

try:
    import readline  # noqa: F401 - importing enables input() history/line-editing
except ImportError:
    pass


def _stdin_lines() -> Iterator[str]:
    while True:
        try:
            yield input()
        except EOFError:
            return


def _build_tools() -> list[Tool]:
    miniflux_config = MinifluxConfig.from_env()
    client = httpx.Client(
        base_url=miniflux_config.base_url,
        headers={"X-Auth-Token": miniflux_config.api_key},
        verify=miniflux_config.tls_verify,
    )
    return [MinifluxQueryTool(client=client)]


def main() -> None:
    if os.environ.get("AGENT_DEBUG"):
        logging.basicConfig(level=logging.DEBUG)

    config = LLMConfig.from_env()
    tools = _build_tools()
    spec = build_rss_spec(config.system_prompt)
    llm_client = OpenAICompatibleLLMClient(
        base_url=config.base_url,
        api_key=config.api_key,
        model=spec.model or config.model,
    )
    store = InMemoryConversationStore()
    agent = LoopAgent(spec, llm_client, store, ContextBuilder(store), ToolRegistry(tools))
    run(agent, _stdin_lines(), sys.stdout)


if __name__ == "__main__":
    main()
