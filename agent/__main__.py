import sys

from agent.adapters.cli import run
from agent.adapters.openai_compatible import OpenAICompatibleLLMClient
from agent.config import LLMConfig
from agent.use_cases.chat import Chat


def main() -> None:
    config = LLMConfig.from_env()
    llm_client = OpenAICompatibleLLMClient(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
    )
    chat = Chat(llm_client)
    run(chat, sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
