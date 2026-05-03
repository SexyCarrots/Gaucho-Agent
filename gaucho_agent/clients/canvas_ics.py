"""Canvas ICS calendar feed client."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx
from icalendar import Calendar, Event as ICSEvent

from gaucho_agent.config import settings
from gaucho_agent.schemas.canvas import CanvasCalendarEvent, EventUpsert
from gaucho_agent.utils.parsing import extract_course_code, strip_html


async def fetch_ics(url: str) -> str:
    """Download a raw ICS feed from the given URL."""
    headers = {"User-Agent": settings.sync_user_agent}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.text


def _to_utc_datetime(value: Any, all_day: bool) -> datetime | None:
    """Coerce an icalendar dt value to a UTC-aware datetime."""
    if value is None:
        return None
    dt = value.dt if hasattr(value, "dt") else value
    if hasattr(dt, "hour"):
        # already a datetime
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    # date-only → midnight UTC
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)


def parse_ics(text: str) -> list[CanvasCalendarEvent]:
    """Parse raw ICS text into a list of CanvasCalendarEvent objects."""
    cal = Calendar.from_ical(text)
    events: list[CanvasCalendarEvent] = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        uid = str(component.get("UID", ""))
        summary = str(component.get("SUMMARY", ""))
        description_raw = component.get("DESCRIPTION")
        description = strip_html(str(description_raw)) if description_raw else None
        url = str(component.get("URL", "")) or None

        dtstart_prop = component.get("DTSTART")
        dtend_prop = component.get("DTEND")

        # Detect all-day: dtstart holds a date (not datetime)
        all_day = False
        if dtstart_prop is not None:
            raw = dtstart_prop.dt if hasattr(dtstart_prop, "dt") else dtstart_prop
            all_day = not hasattr(raw, "hour")

        dtstart = _to_utc_datetime(dtstart_prop, all_day)
        dtend = _to_utc_datetime(dtend_prop, all_day)

        events.append(
            CanvasCalendarEvent(
                uid=uid,
                summary=summary,
                description=description,
                url=url,
                dtstart=dtstart,
                dtend=dtend,
                all_day=all_day,
            )
        )

    return events


def normalize_canvas_event(evt: CanvasCalendarEvent) -> EventUpsert:
    """Convert a CanvasCalendarEvent to an EventUpsert ready for DB write."""
    parsed = extract_course_code(evt.summary)
    course_code: str | None = None
    course_name: str | None = None

    if parsed:
        course_code, _quarter = parsed
        # Strip the bracketed part from the title
        clean_title = re.sub(r"\s*\[.*?\]\s*$", "", evt.summary).strip()
    else:
        clean_title = evt.summary

    # Infer category
    category = "assignment"
    lower = clean_title.lower()
    if any(kw in lower for kw in ("lecture", "section", "lab", "discussion", "class")):
        category = "class"

    return EventUpsert(
        source_kind="canvas_ics",
        external_id=evt.uid,
        title=clean_title,
        category=category,
        course_code=course_code,
        course_name=course_name,
        start_at=evt.dtstart,
        end_at=evt.dtend,
        all_day=evt.all_day,
        description=evt.description,
        url=evt.url,
    )
