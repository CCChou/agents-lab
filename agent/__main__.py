import argparse
import logging
import os
import sys
from collections.abc import Iterator
from datetime import datetime, timedelta

import httpx
from prompt_toolkit import PromptSession
from rich.console import Console

from agent.adapters.cli import MarkdownBlockWriter, prompt_lines, run
from agent.adapters.current_time import CurrentTimeTool
from agent.adapters.http.client import RemoteAgent, RemoteSessions
from agent.adapters.in_memory_store import InMemorySessionStore
from agent.adapters.miniflux import (
    MinifluxArticleReader,
    MinifluxCountEntriesByCategoryTool,
    MinifluxGetEntryTool,
    MinifluxListCategoriesTool,
    MinifluxQueryTool,
)
from agent.adapters.openai_compatible import OpenAICompatibleLLMClient
from agent.adapters.web import FetchPageTool
from agent.agents.rss import build_rss_spec
from agent.config import JobsConfig, LLMConfig, MinifluxConfig
from agent.domain.interfaces import Agent, LLMClient, Notifier, SessionLifecycle
from agent.domain.session import RetentionRule
from agent.domain.tool import Tool
from agent.use_cases.context_builder import ContextBuilder
from agent.use_cases.loop_agent import LoopAgent
from agent.use_cases.run_job import RunJob
from agent.use_cases.session_manager import SessionManager
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
        MinifluxCountEntriesByCategoryTool(client=client),
        MinifluxGetEntryTool(client=client),
        fetch_page,
        SummarizeEntryTool(reader=reader, llm_client=llm_client),
        CurrentTimeTool(clock=lambda: datetime.now().astimezone()),
    ]


SERVE_HOST = "127.0.0.1"  # D-035: no authentication yet, so never listen beyond localhost
DEFAULT_PORT = 8000
DEFAULT_SERVER = f"http://{SERVE_HOST}:{DEFAULT_PORT}"
# A turn can run for minutes with long gaps between events, e.g. while summarize_entry runs.
CHAT_TIMEOUT = httpx.Timeout(10.0, read=600.0)
NOTIFY_TIMEOUT = httpx.Timeout(10.0)
# D-036: the first matching prefix wins; every owner keeps a week, jobs at most seven runs.
SESSION_RETENTION = (
    RetentionRule("job:", max_age=timedelta(days=7), keep_last=7),
    RetentionRule("", max_age=timedelta(days=7)),
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m agent")
    commands = parser.add_subparsers(dest="command")
    serve = commands.add_parser("serve", help=f"run the HTTP API on {SERVE_HOST}")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    chat = commands.add_parser("chat", help="chat in the terminal through a running server")
    chat.add_argument("--server", default=DEFAULT_SERVER)
    return parser.parse_args(argv)


def _build_local_agent() -> tuple[Agent, SessionManager]:
    config = LLMConfig.from_env()
    spec = build_rss_spec(config.system_prompt)
    llm_client = OpenAICompatibleLLMClient(
        base_url=config.base_url,
        api_key=config.api_key,
        model=spec.model or config.model,
        reasoning_effort=config.reasoning_effort,
        temperature=config.temperature,
    )
    tools = _build_tools(llm_client)
    store = InMemorySessionStore()
    agent = LoopAgent(spec, llm_client, store, ContextBuilder(store), ToolRegistry(tools))
    return agent, SessionManager(store, store, rules=SESSION_RETENTION)


def _build_run_job(agent: Agent, sessions: SessionLifecycle) -> RunJob:
    from agent.adapters.jobs_toml import TomlJobSource
    from agent.adapters.notify.slack import SlackWebhookNotifier

    config = JobsConfig.from_env()
    notifiers: dict[str, Notifier] = {}
    if config.slack_webhook_url:
        client = httpx.Client(timeout=NOTIFY_TIMEOUT)
        notifiers["slack"] = SlackWebhookNotifier(client, config.slack_webhook_url)
    return RunJob(agent, sessions, TomlJobSource(config.jobs_file), notifiers)


def _run_terminal(agent: Agent, sessions: SessionLifecycle) -> None:
    if sys.stdin.isatty() and sys.stdout.isatty():
        lines = prompt_lines(PromptSession().prompt)
        run(
            agent,
            sessions,
            lines,
            sys.stdout,
            prompt="",
            text_writer=MarkdownBlockWriter(Console()),
        )
    else:
        run(agent, sessions, _stdin_lines(), sys.stdout)


def main() -> None:
    args = _parse_args()
    if os.environ.get("AGENT_DEBUG"):
        logging.basicConfig(level=logging.DEBUG)

    if args.command == "chat":
        with httpx.Client(base_url=args.server, timeout=CHAT_TIMEOUT) as client:
            _run_terminal(RemoteAgent(client), RemoteSessions(client))
        return

    agent, sessions = _build_local_agent()
    if args.command == "serve":
        import uvicorn

        from agent.adapters.http.api import create_app

        app = create_app(agent, sessions, run_job=_build_run_job(agent, sessions))
        uvicorn.run(app, host=SERVE_HOST, port=args.port)
    else:
        _run_terminal(agent, sessions)


if __name__ == "__main__":
    main()
