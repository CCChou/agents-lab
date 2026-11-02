import logging
import os
import sys
from collections.abc import Iterator
from datetime import datetime

import httpx
from prompt_toolkit import PromptSession
from rich.console import Console

from agent.adapters.cli import MarkdownBlockWriter, prompt_lines, run
from agent.adapters.current_time import CurrentTimeTool
from agent.adapters.in_memory_store import InMemoryConversationStore
from agent.adapters.miniflux import (
    MinifluxArticleReader,
    MinifluxGetEntryTool,
    MinifluxListCategoriesTool,
    MinifluxQueryTool,
)
from agent.adapters.openai_compatible import OpenAICompatibleLLMClient
from agent.adapters.web import FetchPageTool
from agent.agents.rss import build_rss_spec
from agent.config import LLMConfig, MinifluxConfig
from agent.domain.interfaces import LLMClient
from agent.domain.tool import Tool
from agent.use_cases.context_builder import ContextBuilder
from agent.use_cases.loop_agent import LoopAgent
from agent.use_cases.summarize_entry import SummarizeEntryTool
from agent.use_cases.tool_registry import ToolRegistry


def _stdin_lines() -> Iterator[str]:
    while True:
        try:
            yield input()
        except EOFError:
            return


def _build_tools(llm_client: LLMClient) -> list[Tool]:
    miniflux_config = MinifluxConfig.from_env()
    client = httpx.Client(
        base_url=miniflux_config.base_url,
        headers={"X-Auth-Token": miniflux_config.api_key},
        verify=miniflux_config.tls_verify,
    )
    fetch_page = FetchPageTool(client=httpx.Client(timeout=20))
    reader = MinifluxArticleReader(client=client, read_page=fetch_page.read_text)
    return [
        MinifluxQueryTool(client=client),
        MinifluxListCategoriesTool(client=client),
        MinifluxGetEntryTool(client=client),
        fetch_page,
        SummarizeEntryTool(reader=reader, llm_client=llm_client),
        CurrentTimeTool(clock=lambda: datetime.now().astimezone()),
    ]


def main() -> None:
    if os.environ.get("AGENT_DEBUG"):
        logging.basicConfig(level=logging.DEBUG)

    config = LLMConfig.from_env()
    spec = build_rss_spec(config.system_prompt)
    llm_client = OpenAICompatibleLLMClient(
        base_url=config.base_url,
        api_key=config.api_key,
        model=spec.model or config.model,
        reasoning_effort=config.reasoning_effort,
    )
    tools = _build_tools(llm_client)
    store = InMemoryConversationStore()
    agent = LoopAgent(spec, llm_client, store, ContextBuilder(store), ToolRegistry(tools))
    if sys.stdin.isatty() and sys.stdout.isatty():
        lines = prompt_lines(PromptSession().prompt)
        run(agent, lines, sys.stdout, prompt="", text_writer=MarkdownBlockWriter(Console()))
    else:
        run(agent, _stdin_lines(), sys.stdout)


if __name__ == "__main__":
    main()
