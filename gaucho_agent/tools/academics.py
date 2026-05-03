"""Tool: upcoming academic dates from UCSB API data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session

from gaucho_agent.services.retrieval import get_events_in_range
from gaucho_agent.utils.time import format_dt, today_local


def get_upcoming_academic_dates(
    days: int = 14,
    session: Optional[Session] = None,
) -> dict:
    """Return upcoming UCSB academic dates within the next *days* days."""
    if session is None:
        from gaucho_agent.db import get_session
        with get_session() as s:
            return get_upcoming_academic_dates(days=days, session=s)

    today = today_local()
    start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    end = start + timedelta(days=days)

    events = get_events_in_range(
        session, start=start, end=end, source_kind="ucsb_api"
    )

    dates = [
        {
            "id": e.id,
            "title": e.title,
            "category": e.category,
            "start_at": format_dt(e.start_at) if e.start_at else None,
            "end_at": format_dt(e.end_at) if e.end_at else None,
            "all_day": e.all_day,
        }
        for e in events
    ]

    return {
        "query_window": {
            "from": start.date().isoformat(),
            "to": end.date().isoformat(),
            "days": days,
        },
        "dates": dates,
        "count": len(dates),
    }
