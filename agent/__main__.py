import os
import sys

from agent.adapters.cli import run
from agent.adapters.openai_compatible import OpenAICompatibleLLMClient
from agent.use_cases.chat import Chat


def main() -> None:
    llm_client = OpenAICompatibleLLMClient(
        base_url=os.environ["AGENT_LLM_BASE_URL"],
        api_key=os.environ["AGENT_LLM_API_KEY"],
        model=os.environ["AGENT_LLM_MODEL"],
    )
    chat = Chat(llm_client)
    run(chat, sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
