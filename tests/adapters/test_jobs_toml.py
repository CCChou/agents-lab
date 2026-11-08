from pathlib import Path

import pytest

from agent.adapters.jobs_toml import TomlJobSource
from agent.domain.interfaces import JobSource
from agent.domain.job import Job, UnknownJobError


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "jobs.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_satisfies_job_source_port(tmp_path):
    assert isinstance(TomlJobSource(write(tmp_path, "")), JobSource)


def test_get_reads_a_job_by_name(tmp_path):
    path = write(
        tmp_path,
        '[jobs.daily-digest]\nprompt = "今天的趨勢"\nchannels = ["slack"]\n',
    )

    assert TomlJobSource(path).get("daily-digest") == Job(
        name="daily-digest", prompt="今天的趨勢", channels=("slack",)
    )


def test_get_rereads_the_file_so_edits_apply_without_a_restart(tmp_path):
    path = write(tmp_path, '[jobs.a]\nprompt = "old"\nchannels = ["slack"]\n')
    source = TomlJobSource(path)
    source.get("a")

    path.write_text('[jobs.a]\nprompt = "new"\nchannels = ["slack"]\n', encoding="utf-8")

    assert source.get("a").prompt == "new"


def test_get_raises_for_an_unknown_job(tmp_path):
    source = TomlJobSource(write(tmp_path, '[jobs.a]\nprompt = "p"\nchannels = ["slack"]\n'))

    with pytest.raises(UnknownJobError):
        source.get("b")


def test_get_raises_for_an_unknown_job_when_the_file_is_missing(tmp_path):
    with pytest.raises(UnknownJobError):
        TomlJobSource(tmp_path / "missing.toml").get("a")


@pytest.mark.parametrize(
    "body",
    [
        'channels = ["slack"]',
        'prompt = "p"',
        'prompt = ""\nchannels = ["slack"]',
        'prompt = "p"\nchannels = []',
        'prompt = "p"\nchannels = "slack"',
    ],
)
def test_get_rejects_an_invalid_job(tmp_path, body):
    source = TomlJobSource(write(tmp_path, f"[jobs.a]\n{body}\n"))

    with pytest.raises(ValueError):
        source.get("a")
