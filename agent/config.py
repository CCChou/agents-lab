import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            base_url=os.environ["AGENT_LLM_BASE_URL"],
            api_key=os.environ["AGENT_LLM_API_KEY"],
            model=os.environ["AGENT_LLM_MODEL"],
        )
