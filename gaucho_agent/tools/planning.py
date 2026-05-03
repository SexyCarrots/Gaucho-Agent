"""Tool: make a daily plan using the deterministic planner."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session

from gaucho_agent.services.planner import make_plan
from gaucho_agent.services.retrieval import get_events_in_range
from gaucho_agent.utils.time import today_local


def make_daily_plan(
    date: Optional[str] = None,
    available_hours: Optional[int] = None,
    session: Optional[Session] = None,
) -> dict:
    """Generate a structured daily plan for the given date."""
    if session is None:
        from gaucho_agent.db import get_session
        with get_session() as s:
            return make_daily_plan(date=date, available_hours=available_hours, session=s)

    if date:
        try:
            plan_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            plan_date = today_local()
    else:
        plan_date = today_local()

    hours = available_hours if available_hours is not None else 8

    day_start = datetime(plan_date.year, plan_date.month, plan_date.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    week_end = day_start + timedelta(days=7)

    today_schedule = get_events_in_range(session, start=day_start, end=day_end)
    upcoming = get_events_in_range(session, start=day_start, end=week_end, source_kind="canvas_ics")

    plan = make_plan(today_schedule, upcoming, available_hours=hours)
    plan["date"] = plan_date.isoformat()

    return plan
