"""Tool: get upcoming assignments from Canvas calendar."""

from __future__ import annotations

from datetime import timedelta, timezone
from typing import Optional

from sqlmodel import Session

from gaucho_agent.models.event import Event
from gaucho_agent.services.retrieval import get_events_in_range
from gaucho_agent.utils.time import format_dt, now_local


def get_upcoming_assignments(
    days: int = 7,
    course: Optional[str] = None,
    session: Optional[Session] = None,
) -> dict:
    """Return assignments due within the next *days* days from Canvas feed."""
    if session is None:
        from gaucho_agent.db import get_session
        with get_session() as s:
            return get_upcoming_assignments(days=days, course=course, session=s)

    now = now_local().astimezone(timezone.utc).replace(tzinfo=None)
    end = now + timedelta(days=days)

    events = get_events_in_range(
        session, start=now, end=end, source_kind="canvas_ics"
    )

    if course:
        events = [
            e for e in events
            if e.course_code and course.lower() in e.course_code.lower()
        ]

    assignments = [
        {
            "id": e.id,
            "title": e.title,
            "course_code": e.course_code,
            "course_name": e.course_name,
            "due_at": format_dt(e.start_at) if e.start_at else None,
            "url": e.url,
            "description": e.description,
        }
        for e in events
    ]

    return {
        "query_window": {
            "from": now.isoformat(),
            "to": end.isoformat(),
            "days": days,
        },
        "assignments": assignments,
        "count": len(assignments),
    }
