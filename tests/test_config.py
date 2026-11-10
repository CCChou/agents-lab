from pathlib import Path

import pytest

from agent.config import ConfigError, load_config, resolve_config_path

MINIMAL = """
[llm]
base_url = "https://api.openai.com/v1"
model = "gpt-6-luna"

[miniflux]
base_url = "https://miniflux.example.test"
"""

SECRETS = {"AGENT_LLM_API_KEY": "llm-key", "MINIFLUX_API_KEY": "miniflux-key"}


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_config_reads_settings_from_the_file_and_secrets_from_env(tmp_path):
    path = _write(tmp_path, MINIMAL)

    config = load_config(path, SECRETS)

    assert config.path == path
    assert config.llm.base_url == "https://api.openai.com/v1"
    assert config.llm.model == "gpt-6-luna"
    assert config.llm.api_key == "llm-key"
    assert config.miniflux.base_url == "https://miniflux.example.test"
    assert config.miniflux.api_key == "miniflux-key"


def test_load_config_defaults_optional_settings(tmp_path):
    config = load_config(_write(tmp_path, MINIMAL), SECRETS)

    assert config.debug is False
    assert config.slack_webhook_url is None
    assert config.llm.system_prompt is None
    assert config.llm.reasoning_effort is None
    assert config.llm.temperature is None
    assert config.miniflux.ca_bundle_path is None
    assert config.miniflux.verify_ssl is True
    assert config.miniflux.tls_verify is True


def test_load_config_reads_optional_settings(tmp_path):
    path = _write(
        tmp_path,
        """
debug = true

[llm]
base_url = "https://api.groq.com/openai/v1"
model = "qwen/qwen3.8-27b"
system_prompt = "You are a helpful assistant."
reasoning_effort = "none"
temperature = 0.1

[miniflux]
base_url = "https://miniflux.example.test"
ca_bundle = "/etc/ssl/miniflux-ca.pem"
""",
    )

    config = load_config(path, SECRETS | {"SLACK_WEBHOOK_URL": "https://hooks.slack.test/x"})

    assert config.debug is True
    assert config.slack_webhook_url == "https://hooks.slack.test/x"
    assert config.llm.system_prompt == "You are a helpful assistant."
    assert config.llm.reasoning_effort == "none"
    assert config.llm.temperature == 0.1
    assert config.miniflux.ca_bundle_path == "/etc/ssl/miniflux-ca.pem"
    assert config.miniflux.tls_verify == "/etc/ssl/miniflux-ca.pem"


def test_load_config_accepts_an_integer_temperature(tmp_path):
    path = _write(tmp_path, MINIMAL.replace('model = "gpt-6-luna"', 'model = "m"\ntemperature = 1'))

    config = load_config(path, SECRETS)

    assert config.llm.temperature == 1.0
    assert isinstance(config.llm.temperature, float)


def test_load_config_treats_an_empty_slack_webhook_as_unset(tmp_path):
    config = load_config(_write(tmp_path, MINIMAL), SECRETS | {"SLACK_WEBHOOK_URL": ""})

    assert config.slack_webhook_url is None


def test_verify_ssl_false_disables_tls_verification_even_with_a_ca_bundle(tmp_path):
    path = _write(
        tmp_path,
        MINIMAL + 'verify_ssl = false\nca_bundle = "/etc/ssl/miniflux-ca.pem"\n',
    )

    config = load_config(path, SECRETS)

    assert config.miniflux.verify_ssl is False
    assert config.miniflux.tls_verify is False


@pytest.mark.parametrize(
    ("text", "field"),
    [
        (MINIMAL.replace('base_url = "https://api.openai.com/v1"\n', ""), "llm.base_url"),
        (MINIMAL.replace('model = "gpt-6-luna"', "model = 1"), "llm.model"),
        (
            MINIMAL.replace('model = "gpt-6-luna"', 'model = "m"\ntemperature = "hot"'),
            "llm.temperature",
        ),
        (MINIMAL.replace("[miniflux]", "[other]"), "miniflux.base_url"),
        (MINIMAL + 'verify_ssl = "false"\n', "miniflux.verify_ssl"),
        ('debug = "yes"\n' + MINIMAL, "debug"),
    ],
)
def test_load_config_names_the_field_that_is_missing_or_has_the_wrong_type(tmp_path, text, field):
    with pytest.raises(ConfigError, match=field):
        load_config(_write(tmp_path, text), SECRETS)


@pytest.mark.parametrize("name", ["AGENT_LLM_API_KEY", "MINIFLUX_API_KEY"])
def test_load_config_requires_each_secret_in_env(tmp_path, name):
    env = {key: value for key, value in SECRETS.items() if key != name}

    with pytest.raises(ConfigError, match=name):
        load_config(_write(tmp_path, MINIMAL), env)


def test_load_config_reports_a_missing_file(tmp_path):
    path = tmp_path / "missing.toml"

    with pytest.raises(ConfigError, match="missing.toml"):
        load_config(path, SECRETS)


def test_load_config_reports_invalid_toml(tmp_path):
    with pytest.raises(ConfigError, match="config.toml"):
        load_config(_write(tmp_path, "[llm\n"), SECRETS)


def test_resolve_config_path_prefers_the_argument_over_env():
    path = resolve_config_path("/srv/a.toml", {"AGENT_CONFIG": "/etc/agent/config.toml"})

    assert path == Path("/srv/a.toml")


def test_resolve_config_path_falls_back_to_agent_config():
    path = resolve_config_path(None, {"AGENT_CONFIG": "/etc/agent/config.toml"})

    assert path == Path("/etc/agent/config.toml")


@pytest.mark.parametrize("env", [{}, {"AGENT_CONFIG": ""}])
def test_resolve_config_path_requires_one_of_them(env):
    with pytest.raises(ConfigError, match="--config"):
        resolve_config_path(None, env)
