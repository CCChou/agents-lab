"""Settings come from one TOML file; only secrets come from env (D-038)."""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_ENV = "AGENT_CONFIG"


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    system_prompt: str | None = None
    reasoning_effort: str | None = None
    temperature: float | None = None


@dataclass(frozen=True)
class MinifluxConfig:
    base_url: str
    api_key: str
    ca_bundle_path: str | None = None
    verify_ssl: bool = True

    @property
    def tls_verify(self) -> bool | str:
        if not self.verify_ssl:
            return False
        if self.ca_bundle_path:
            return self.ca_bundle_path
        return True


@dataclass(frozen=True)
class AppConfig:
    """`[jobs]` in the same file is read by `TomlJobSource` on every run, not here (D-037)."""

    path: Path
    llm: LLMConfig
    miniflux: MinifluxConfig
    slack_webhook_url: str | None = None
    debug: bool = False


def resolve_config_path(arg: str | None, env: Mapping[str, str]) -> Path:
    value = arg or env.get(CONFIG_ENV)
    if not value:
        raise ConfigError(f"no config file: pass --config <path> or set {CONFIG_ENV}")
    return Path(value)


def load_config(path: Path, env: Mapping[str, str]) -> AppConfig:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"{path} does not exist") from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from None

    llm = _table(data, "llm")
    miniflux = _table(data, "miniflux")
    temperature = _optional(llm, "llm.temperature", (int, float))
    return AppConfig(
        path=path,
        llm=LLMConfig(
            base_url=_required(llm, "llm.base_url"),
            api_key=_secret(env, "AGENT_LLM_API_KEY"),
            model=_required(llm, "llm.model"),
            system_prompt=_optional(llm, "llm.system_prompt", str),
            reasoning_effort=_optional(llm, "llm.reasoning_effort", str),
            temperature=float(temperature) if temperature is not None else None,
        ),
        miniflux=MinifluxConfig(
            base_url=_required(miniflux, "miniflux.base_url"),
            api_key=_secret(env, "MINIFLUX_API_KEY"),
            ca_bundle_path=_optional(miniflux, "miniflux.ca_bundle", str),
            verify_ssl=_flag(miniflux, "miniflux.verify_ssl", default=True),
        ),
        slack_webhook_url=env.get("SLACK_WEBHOOK_URL") or None,
        debug=_flag(data, "debug", default=False),
    )


def _table(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    table = data.get(name, {})
    if not isinstance(table, dict):
        raise ConfigError(f"[{name}] must be a table")
    return table


def _key(field: str) -> str:
    return field.rsplit(".", 1)[-1]


def _optional(table: Mapping[str, Any], field: str, types: type | tuple[type, ...]) -> Any:
    value = table.get(_key(field))
    # bool is an int in Python, but `temperature = true` is a mistake, not 1.0
    if value is not None and (isinstance(value, bool) or not isinstance(value, types)):
        raise ConfigError(f"{field} has the wrong type: {value!r}")
    return value


def _required(table: Mapping[str, Any], field: str) -> str:
    value = _optional(table, field, str)
    if not value:
        raise ConfigError(f"{field} is required")
    return value


def _flag(table: Mapping[str, Any], field: str, *, default: bool) -> bool:
    value = table.get(_key(field), default)
    if not isinstance(value, bool):
        raise ConfigError(f"{field} must be true or false: {value!r}")
    return value


def _secret(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if not value:
        raise ConfigError(f"{name} must be set in the environment")
    return value
