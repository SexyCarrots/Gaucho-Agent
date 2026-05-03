"""Tools: today's schedule and workload summary."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session

from gaucho_agent.services.retrieval import get_events_in_range
from gaucho_agent.utils.time import format_dt, now_local, today_local


def get_today_schedule(session: Optional[Session] = None) -> dict:
    """Return all events scheduled for today."""
    if session is None:
        from gaucho_agent.db import get_session
        with get_session() as s:
            return get_today_schedule(session=s)

    today = today_local()
    start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    events = get_events_in_range(session, start=start, end=end)

    items = [
        {
            "id": e.id,
            "title": e.title,
            "course_code": e.course_code,
            "start_at": format_dt(e.start_at) if e.start_at else None,
            "end_at": format_dt(e.end_at) if e.end_at else None,
            "location": e.location,
            "all_day": e.all_day,
        }
        for e in events
    ]

    return {
        "date": today.isoformat(),
        "events": items,
        "count": len(items),
    }


def summarize_workload(days: int = 7, session: Optional[Session] = None) -> dict:
    """Summarize event distribution over the next N days."""
    if session is None:
        from gaucho_agent.db import get_session
        with get_session() as s:
            return summarize_workload(days=days, session=s)

    today = today_local()
    start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    end = start + timedelta(days=days)

    events = get_events_in_range(session, start=start, end=end)

    by_day: dict[str, list[dict]] = {}
    for e in events:
        day_key = e.start_at.date().isoformat() if e.start_at else "unknown"
        if day_key not in by_day:
            by_day[day_key] = []
        by_day[day_key].append(
            {
                "id": e.id,
                "title": e.title,
                "course_code": e.course_code,
                "start_at": format_dt(e.start_at) if e.start_at else None,
                "end_at": format_dt(e.end_at) if e.end_at else None,
                "location": e.location,
                "all_day": e.all_day,
            }
        )

    return {
        "query_window": {
            "from": start.date().isoformat(),
            "to": end.date().isoformat(),
            "days": days,
        },
        "total_events": len(events),
        "by_day": by_day,
    }
