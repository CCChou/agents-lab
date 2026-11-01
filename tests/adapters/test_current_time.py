from datetime import datetime, timedelta, timezone

from agent.adapters.current_time import CurrentTimeTool
from agent.domain.tool import Tool

TAIPEI = timezone(timedelta(hours=8))


def test_satisfies_tool_port():
    assert isinstance(CurrentTimeTool(clock=lambda: datetime.now(TAIPEI)), Tool)


def test_takes_no_arguments():
    tool = CurrentTimeTool(clock=lambda: datetime.now(TAIPEI))

    assert tool.parameters_schema["properties"] == {}


def test_run_returns_iso_time_with_offset_and_weekday():
    tool = CurrentTimeTool(clock=lambda: datetime(2026, 11, 1, 14, 30, 5, 123, tzinfo=TAIPEI))

    assert tool.run({}) == "2026-11-01T14:30:05+08:00 (Sunday)"


def test_run_reads_the_clock_on_every_call():
    times = iter(
        [
            datetime(2026, 11, 1, 23, 59, tzinfo=TAIPEI),
            datetime(2026, 11, 2, 0, 1, tzinfo=TAIPEI),
        ]
    )
    tool = CurrentTimeTool(clock=lambda: next(times))

    assert tool.run({}).startswith("2026-11-01")
    assert tool.run({}).startswith("2026-11-02")
