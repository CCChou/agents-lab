import pytest

from agent.config import LLMConfig


def test_from_env_reads_all_three_values(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("AGENT_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_LLM_MODEL", "deepseek/deepseek-chat-v3.1:free")

    config = LLMConfig.from_env()

    assert config.base_url == "https://openrouter.ai/api/v1"
    assert config.api_key == "test-key"
    assert config.model == "deepseek/deepseek-chat-v3.1:free"


def test_from_env_raises_when_a_variable_is_missing(monkeypatch):
    monkeypatch.delenv("AGENT_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("AGENT_LLM_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_LLM_MODEL", raising=False)

    with pytest.raises(KeyError):
        LLMConfig.from_env()
