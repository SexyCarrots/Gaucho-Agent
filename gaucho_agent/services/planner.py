"""Deterministic heuristic daily planner."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from gaucho_agent.models.event import Event
from gaucho_agent.utils.time import format_dt

# Keywords that elevate urgency
_HIGH_PRIORITY_KEYWORDS = {"midterm", "final", "project", "proposal", "exam", "quiz", "defense"}

# Time blocks (hour ranges, inclusive start exclusive end)
_BLOCKS = {
    "morning": (8, 12),
    "afternoon": (12, 17),
    "evening": (17, 21),
}


def _naive_utc(dt: datetime) -> datetime:
    """Strip timezone info so naive and aware datetimes can be compared."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def compute_urgency(event: Event, now: datetime) -> int:
    """Return an urgency score 0-100 (higher = more urgent)."""
    score = 0
    now_naive = _naive_utc(now)
    if event.start_at:
        event_dt = _naive_utc(event.start_at)
        delta = event_dt - now_naive
        hours_until = delta.total_seconds() / 3600
        if hours_until < 0:
            return 0  # already past
        if hours_until < 24:
            score += 60
        elif hours_until < 48:
            score += 40
        elif hours_until < 96:
            score += 20
        else:
            score += 5

    title_lower = (event.title or "").lower()
    if any(kw in title_lower for kw in _HIGH_PRIORITY_KEYWORDS):
        score += 30

    return min(score, 100)


def _hour_of(dt: datetime) -> int:
    """Return local hour of a UTC datetime (naive conversion using UTC)."""
    return dt.hour  # Caller already passes timezone-aware or converts


def make_plan(
    today_schedule: list[Event],
    upcoming: list[Event],
    available_hours: int = 8,
) -> dict[str, Any]:
    """Build a structured daily plan dict from schedule and upcoming events."""
    now = datetime.now(tz=timezone.utc)

    # Occupied slots from today's schedule (existing classes/events)
    occupied_hours: set[int] = set()
    for evt in today_schedule:
        if evt.start_at and evt.end_at and not evt.all_day:
            h = _naive_utc(evt.start_at).hour
            while h < _naive_utc(evt.end_at).hour:
                occupied_hours.add(h)
                h += 1

    # Sort upcoming by urgency (descending) then by start time
    scored = [(compute_urgency(e, now), e) for e in upcoming]
    scored.sort(key=lambda x: (-x[0], _naive_utc(x[1].start_at) if x[1].start_at else datetime.max))

    urgent: list[str] = []
    morning: list[str] = []
    afternoon: list[str] = []
    evening: list[str] = []
    notes: list[str] = []

    hours_allocated = 0

    for score, evt in scored:
        if hours_allocated >= available_hours:
            notes.append(f"Deferred (no capacity): {evt.title}")
            continue

        label = evt.title
        if evt.start_at:
            label += f" – due {format_dt(evt.start_at)}"

        if score >= 50:
            urgent.append(label)
            hours_allocated += 2
            continue

        # Place into a block that isn't fully occupied
        placed = False
        for block_name, (start_h, end_h) in _BLOCKS.items():
            free = [h for h in range(start_h, end_h) if h not in occupied_hours]
            if len(free) >= 1:
                if block_name == "morning":
                    morning.append(label)
                elif block_name == "afternoon":
                    afternoon.append(label)
                else:
                    evening.append(label)
                hours_allocated += 1
                placed = True
                break

        if not placed:
            notes.append(f"No free block found for: {evt.title}")

    return {
        "available_hours": available_hours,
        "urgent": urgent,
        "morning": morning,
        "afternoon": afternoon,
        "evening": evening,
        "notes": notes,
    }
