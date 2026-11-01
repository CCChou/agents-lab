from collections.abc import Callable
from datetime import datetime
from typing import Any, ClassVar


class CurrentTimeTool:
    name = "get_current_time"
    description = (
        "Get the current date, time, weekday and UTC offset. Call this before answering "
        "or querying anything that depends on the current date, such as 'today' or "
        "'last week'. Never guess the date or reuse an earlier result."
    )
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    def __init__(self, *, clock: Callable[[], datetime]) -> None:
        self._clock = clock

    def run(self, arguments: dict[str, Any]) -> str:
        now = self._clock()
        return f"{now.isoformat(timespec='seconds')} ({now:%A})"
