from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class SessionInfo:
    session_id: str
    created_at: datetime


@dataclass(frozen=True)
class RetentionRule:
    """Sessions of matching owners are removed when either limit is exceeded (D-036)."""

    owner_prefix: str
    max_age: timedelta | None = None
    keep_last: int | None = None
