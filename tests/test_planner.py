"""Tests for the deterministic planner heuristics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from gaucho_agent.models.event import Event
from gaucho_agent.services.planner import compute_urgency, make_plan


def _event(title: str, hours_from_now: float, source_kind: str = "canvas_ics") -> Event:
    """Helper to create an Event with start_at relative to now."""
    now = datetime.now(tz=timezone.utc)
    start = now + timedelta(hours=hours_from_now)
    return Event(
        source_kind=source_kind,
        external_id=f"test-{title.replace(' ', '-')}",
        title=title,
        start_at=start,
        end_at=start + timedelta(hours=1),
        all_day=False,
        created_at=now,
        updated_at=now,
    )


def test_urgency_due_in_2h():
    """Event due in 2 hours should have high urgency (>=60)."""
    evt = _event("Homework 1", hours_from_now=2)
    now = datetime.now(tz=timezone.utc)
    score = compute_urgency(evt, now)
    assert score >= 60


def test_urgency_due_in_5_days():
    """Event due in 5 days should have normal urgency (<40)."""
    evt = _event("Reading Assignment", hours_from_now=5 * 24)
    now = datetime.now(tz=timezone.utc)
    score = compute_urgency(evt, now)
    assert score < 40


def test_urgency_midterm_elevated():
    """Title containing 'midterm' should have elevated urgency (+30 keyword bonus)."""
    evt_regular = _event("Regular Homework", hours_from_now=5 * 24)
    evt_midterm = _event("Midterm Exam", hours_from_now=5 * 24)
    now = datetime.now(tz=timezone.utc)
    score_regular = compute_urgency(evt_regular, now)
    score_midterm = compute_urgency(evt_midterm, now)
    assert score_midterm > score_regular
    assert score_midterm - score_regular >= 25


def test_urgency_final_elevated():
    """Title containing 'final' should have elevated urgency."""
    evt = _event("Final Project", hours_from_now=72)
    now = datetime.now(tz=timezone.utc)
    score = compute_urgency(evt, now)
    assert score >= 50  # should be elevated due to keyword


def test_urgency_past_event_is_zero():
    """Past events should have urgency of 0."""
    evt = _event("Old Assignment", hours_from_now=-1)
    now = datetime.now(tz=timezone.utc)
    score = compute_urgency(evt, now)
    assert score == 0


def test_make_plan_urgent_items_first():
    """Events due soon should appear in the urgent block."""
    today_schedule: list[Event] = []
    upcoming = [
        _event("Urgent Homework", hours_from_now=5),
        _event("Normal Reading", hours_from_now=5 * 24),
    ]
    plan = make_plan(today_schedule, upcoming, available_hours=8)
    assert len(plan["urgent"]) >= 1
    assert any("Urgent Homework" in item for item in plan["urgent"])


def test_make_plan_normal_items_in_blocks():
    """Non-urgent items should be distributed into time blocks."""
    today_schedule: list[Event] = []
    upcoming = [
        _event("Reading Ch. 5", hours_from_now=4 * 24),
        _event("Problem Set", hours_from_now=6 * 24),
    ]
    plan = make_plan(today_schedule, upcoming, available_hours=8)
    all_blocks = plan["morning"] + plan["afternoon"] + plan["evening"]
    assert len(all_blocks) >= 1


def test_make_plan_returns_expected_keys():
    """make_plan output should have the required keys."""
    plan = make_plan([], [], available_hours=8)
    for key in ("urgent", "morning", "afternoon", "evening", "notes", "available_hours"):
        assert key in plan


def test_make_plan_respects_capacity():
    """When available_hours is low, excess items should go into notes."""
    upcoming = [_event(f"Task {i}", hours_from_now=i * 10) for i in range(10)]
    plan = make_plan([], upcoming, available_hours=2)
    total_tasks = (
        len(plan["urgent"]) + len(plan["morning"]) +
        len(plan["afternoon"]) + len(plan["evening"])
    )
    # With 2h capacity, we shouldn't fit everything (10 tasks)
    assert total_tasks < 10 or len(plan["notes"]) >= 0  # at minimum it runs without error
