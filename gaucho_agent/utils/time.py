"""Time utilities – timezone-aware helpers."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from gaucho_agent.config import settings


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.local_timezone)


def now_local() -> datetime:
    """Current time in the configured local timezone."""
    return datetime.now(tz=_tz())


def today_local() -> date:
    """Today's date in the configured local timezone."""
    return now_local().date()


def parse_dt(value: date | datetime | str) -> datetime:
    """Coerce a date, datetime, or ISO string to a timezone-aware UTC datetime."""
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = datetime.strptime(value[:10], "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError(f"Cannot parse datetime: {value!r}") from exc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    # date-only → midnight UTC
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def format_dt(dt: datetime | None) -> str:
    """Format a UTC datetime as a human-readable local string."""
    if dt is None:
        return "N/A"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(_tz())
    return local.strftime("%a %b %-d, %Y %-I:%M %p %Z")
