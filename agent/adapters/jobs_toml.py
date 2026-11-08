import tomllib
from pathlib import Path

from agent.domain.job import Job, UnknownJobError


class TomlJobSource:
    """Reads `[jobs.<name>]` tables from a TOML file on every call, so edits need no restart."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self, name: str) -> Job:
        try:
            data = tomllib.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise UnknownJobError(f"{name}: {self._path} does not exist") from None
        table = data.get("jobs", {}).get(name)
        if table is None:
            raise UnknownJobError(f"{name}: not defined in {self._path}")
        prompt = table.get("prompt")
        channels = table.get("channels")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"{name}: prompt must be a non-empty string")
        if not isinstance(channels, list) or not channels:
            raise ValueError(f"{name}: channels must be a non-empty list")
        if not all(isinstance(channel, str) for channel in channels):
            raise ValueError(f"{name}: channels must be strings")
        return Job(name=name, prompt=prompt, channels=tuple(channels))
