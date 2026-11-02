import pytest

from agent.config import LLMConfig, MinifluxConfig


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


def test_from_env_reads_optional_system_prompt(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("AGENT_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_LLM_MODEL", "deepseek/deepseek-chat-v3.1:free")
    monkeypatch.setenv("AGENT_SYSTEM_PROMPT", "You are a helpful assistant.")

    config = LLMConfig.from_env()

    assert config.system_prompt == "You are a helpful assistant."


def test_from_env_defaults_system_prompt_to_none_when_unset(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("AGENT_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_LLM_MODEL", "deepseek/deepseek-chat-v3.1:free")
    monkeypatch.delenv("AGENT_SYSTEM_PROMPT", raising=False)

    config = LLMConfig.from_env()

    assert config.system_prompt is None


def test_from_env_reads_optional_reasoning_effort(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("AGENT_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_LLM_MODEL", "gpt-6-luna")
    monkeypatch.setenv("AGENT_LLM_REASONING_EFFORT", "none")

    config = LLMConfig.from_env()

    assert config.reasoning_effort == "none"


def test_from_env_defaults_reasoning_effort_to_none_when_unset(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("AGENT_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_LLM_MODEL", "deepseek/deepseek-chat-v3.1:free")
    monkeypatch.delenv("AGENT_LLM_REASONING_EFFORT", raising=False)

    config = LLMConfig.from_env()

    assert config.reasoning_effort is None


def test_from_env_reads_optional_temperature(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("AGENT_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_LLM_MODEL", "qwen/qwen3.8-27b")
    monkeypatch.setenv("AGENT_LLM_TEMPERATURE", "0.1")

    config = LLMConfig.from_env()

    assert config.temperature == 0.1


def test_from_env_defaults_temperature_to_none_when_unset(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("AGENT_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_LLM_MODEL", "qwen/qwen3.8-27b")
    monkeypatch.delenv("AGENT_LLM_TEMPERATURE", raising=False)

    config = LLMConfig.from_env()

    assert config.temperature is None


def test_miniflux_config_from_env_reads_both_values(monkeypatch):
    monkeypatch.setenv("MINIFLUX_BASE_URL", "https://miniflux.example.test")
    monkeypatch.setenv("MINIFLUX_API_KEY", "test-token")

    config = MinifluxConfig.from_env()

    assert config.base_url == "https://miniflux.example.test"
    assert config.api_key == "test-token"


def test_miniflux_config_from_env_raises_when_a_variable_is_missing(monkeypatch):
    monkeypatch.delenv("MINIFLUX_BASE_URL", raising=False)
    monkeypatch.delenv("MINIFLUX_API_KEY", raising=False)

    with pytest.raises(KeyError):
        MinifluxConfig.from_env()


def test_miniflux_config_defaults_to_verified_tls_with_no_ca_bundle(monkeypatch):
    monkeypatch.setenv("MINIFLUX_BASE_URL", "https://miniflux.example.test")
    monkeypatch.setenv("MINIFLUX_API_KEY", "test-token")
    monkeypatch.delenv("MINIFLUX_CA_BUNDLE", raising=False)
    monkeypatch.delenv("MINIFLUX_VERIFY_SSL", raising=False)

    config = MinifluxConfig.from_env()

    assert config.ca_bundle_path is None
    assert config.verify_ssl is True
    assert config.tls_verify is True


def test_miniflux_config_reads_ca_bundle_path_and_uses_it_for_tls_verify(monkeypatch):
    monkeypatch.setenv("MINIFLUX_BASE_URL", "https://miniflux.example.test")
    monkeypatch.setenv("MINIFLUX_API_KEY", "test-token")
    monkeypatch.setenv("MINIFLUX_CA_BUNDLE", "/etc/ssl/miniflux-ca.pem")
    monkeypatch.delenv("MINIFLUX_VERIFY_SSL", raising=False)

    config = MinifluxConfig.from_env()

    assert config.ca_bundle_path == "/etc/ssl/miniflux-ca.pem"
    assert config.tls_verify == "/etc/ssl/miniflux-ca.pem"


@pytest.mark.parametrize("value", ["false", "False", "0", "no", "NO"])
def test_miniflux_config_verify_ssl_false_disables_tls_verification(monkeypatch, value):
    monkeypatch.setenv("MINIFLUX_BASE_URL", "https://miniflux.example.test")
    monkeypatch.setenv("MINIFLUX_API_KEY", "test-token")
    monkeypatch.setenv("MINIFLUX_VERIFY_SSL", value)

    config = MinifluxConfig.from_env()

    assert config.verify_ssl is False
    assert config.tls_verify is False


def test_miniflux_config_verify_ssl_false_overrides_ca_bundle_path(monkeypatch):
    monkeypatch.setenv("MINIFLUX_BASE_URL", "https://miniflux.example.test")
    monkeypatch.setenv("MINIFLUX_API_KEY", "test-token")
    monkeypatch.setenv("MINIFLUX_VERIFY_SSL", "false")
    monkeypatch.setenv("MINIFLUX_CA_BUNDLE", "/etc/ssl/miniflux-ca.pem")

    config = MinifluxConfig.from_env()

    assert config.tls_verify is False
