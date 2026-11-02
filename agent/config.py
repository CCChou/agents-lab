import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    system_prompt: str | None = None
    reasoning_effort: str | None = None
    temperature: float | None = None

    @classmethod
    def from_env(cls) -> "LLMConfig":
        temperature = os.environ.get("AGENT_LLM_TEMPERATURE")
        return cls(
            base_url=os.environ["AGENT_LLM_BASE_URL"],
            api_key=os.environ["AGENT_LLM_API_KEY"],
            model=os.environ["AGENT_LLM_MODEL"],
            system_prompt=os.environ.get("AGENT_SYSTEM_PROMPT"),
            reasoning_effort=os.environ.get("AGENT_LLM_REASONING_EFFORT"),
            temperature=float(temperature) if temperature else None,
        )


_FALSY_VALUES = {"false", "0", "no"}


@dataclass(frozen=True)
class MinifluxConfig:
    base_url: str
    api_key: str
    ca_bundle_path: str | None = None
    verify_ssl: bool = True

    @classmethod
    def from_env(cls) -> "MinifluxConfig":
        return cls(
            base_url=os.environ["MINIFLUX_BASE_URL"],
            api_key=os.environ["MINIFLUX_API_KEY"],
            ca_bundle_path=os.environ.get("MINIFLUX_CA_BUNDLE"),
            verify_ssl=os.environ.get("MINIFLUX_VERIFY_SSL", "true").lower() not in _FALSY_VALUES,
        )

    @property
    def tls_verify(self) -> bool | str:
        if not self.verify_ssl:
            return False
        if self.ca_bundle_path:
            return self.ca_bundle_path
        return True
