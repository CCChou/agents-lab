import logging
import os
import sys
from collections.abc import Iterator
from typing import TextIO

import httpx
from rich.console import Console
from rich.markdown import Markdown

from agent.adapters.cli import run
from agent.adapters.miniflux import MinifluxQueryTool
from agent.adapters.openai_compatible import OpenAICompatibleLLMClient
from agent.config import LLMConfig, MinifluxConfig
from agent.domain.tool import Tool
from agent.use_cases.chat import Chat

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


def _render_markdown(text: str, output: TextIO) -> None:
    Console(file=output).print(Markdown(text))


def _build_tools() -> list[Tool]:
    if "MINIFLUX_BASE_URL" not in os.environ or "MINIFLUX_API_KEY" not in os.environ:
        return []
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
    llm_client = OpenAICompatibleLLMClient(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
    )
    chat = Chat(llm_client, system_prompt=config.system_prompt, tools=_build_tools())
    run(chat, _stdin_lines(), sys.stdout, render=_render_markdown)


if __name__ == "__main__":
    main()
