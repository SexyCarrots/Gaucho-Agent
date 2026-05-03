"""Tests for tool functions using in-memory SQLite seeded from fixtures."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from gaucho_agent.models.dining import DiningCommonsStatus, DiningMenuItem
from gaucho_agent.models.event import Event
from gaucho_agent.tools.assignments import get_upcoming_assignments
from gaucho_agent.tools.dining import get_dining_commons_status, get_dining_menu
from gaucho_agent.tools.schedule import get_today_schedule, summarize_workload
from gaucho_agent.tools.academics import get_upcoming_academic_dates

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine for the test suite."""
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(e)
    return e


@pytest.fixture(scope="module")
def seeded_session(engine):
    """Session pre-seeded with fixture data."""
    now = datetime.now(tz=timezone.utc).replace(tzinfo=None)

    # --- Events from sample.ics (manually reconstructed) ---
    events = [
        Event(
            source_kind="canvas_ics",
            external_id="evt-hw3",
            title="Homework 3",
            category="assignment",
            course_code="CMPSC 291A",
            start_at=now + timedelta(days=3),
            end_at=now + timedelta(days=3),
            all_day=False,
            created_at=now,
            updated_at=now,
        ),
        Event(
            source_kind="canvas_ics",
            external_id="evt-midterm",
            title="Midterm Exam Study Guide",
            category="assignment",
            course_code="CMPSC 130A",
            start_at=now + timedelta(days=5),
            end_at=now + timedelta(days=5),
            all_day=False,
            created_at=now,
            updated_at=now,
        ),
        Event(
            source_kind="canvas_ics",
            external_id="evt-lecture",
            title="Lecture: Algorithms",
            category="class",
            course_code="CMPSC 291A",
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(hours=3, minutes=15),
            all_day=False,
            location="Phelps 1448",
            created_at=now,
            updated_at=now,
        ),
        Event(
            source_kind="ucsb_api",
            external_id="evt-career-fair",
            title="UCSB Career Fair",
            category="event",
            start_at=now + timedelta(days=8),
            end_at=now + timedelta(days=8, hours=5),
            all_day=False,
            location="Events Center",
            created_at=now,
            updated_at=now,
        ),
        Event(
            source_kind="ucsb_api",
            external_id="evt-academic-1",
            title="S26 – Last Day of Classes",
            category="academic",
            start_at=now + timedelta(days=10),
            end_at=now + timedelta(days=10),
            all_day=True,
            created_at=now,
            updated_at=now,
        ),
    ]

    # --- Dining commons ---
    commons_data = json.loads((FIXTURES / "ucsb" / "dining_commons.json").read_text())
    commons = [
        DiningCommonsStatus(
            commons_code=c["code"].strip(),
            commons_name=c["name"],
            has_sack_meal=c.get("hasSackMeal", False),
            has_take_out_meal=c.get("hasTakeOutMeal", False),
            has_dining_cam=c.get("hasDiningCam", False),
            updated_at=now,
        )
        for c in commons_data
    ]

    # --- Dining menu items ---
    menu_data = json.loads((FIXTURES / "ucsb" / "dining_menu.json").read_text())
    today = date.today()
    menu_items = [
        DiningMenuItem(
            commons_code=m["commons_code"],
            commons_name=m["commons_name"],
            meal_code=m["meal_code"],
            name=m["name"],
            station_name=m.get("station"),
            menu_date=today,
            updated_at=now,
        )
        for m in menu_data
    ]

    with Session(engine) as session:
        for obj in events + commons + menu_items:
            session.add(obj)
        session.commit()
        yield session


# ---------------------------------------------------------------------------
# Assignment tool tests
# ---------------------------------------------------------------------------

def test_get_upcoming_assignments_count(seeded_session):
    """Should return 2 canvas_ics assignments in a 7-day window."""
    result = get_upcoming_assignments(days=7, session=seeded_session)
    # hw3 (3 days) and midterm (5 days) are within 7 days; lecture is a class not assignment
    assignments = result["assignments"]
    assert result["count"] >= 2


def test_get_upcoming_assignments_course_filter(seeded_session):
    """Filtering by course should narrow results."""
    result = get_upcoming_assignments(days=7, course="CMPSC 291A", session=seeded_session)
    for a in result["assignments"]:
        assert "CMPSC 291A" in (a["course_code"] or "")


def test_get_upcoming_assignments_returns_required_keys(seeded_session):
    """Each assignment dict must have required keys."""
    result = get_upcoming_assignments(days=7, session=seeded_session)
    for a in result["assignments"]:
        for key in ("id", "title", "course_code", "due_at"):
            assert key in a


# ---------------------------------------------------------------------------
# Schedule tool tests
# ---------------------------------------------------------------------------

def test_get_today_schedule_returns_structure(seeded_session):
    """get_today_schedule should return date, events, count."""
    result = get_today_schedule(session=seeded_session)
    assert "date" in result
    assert "events" in result
    assert "count" in result


def test_summarize_workload_returns_by_day(seeded_session):
    """summarize_workload should return a by_day dict."""
    result = summarize_workload(days=14, session=seeded_session)
    assert "by_day" in result
    assert "total_events" in result
    assert result["total_events"] >= 0


# ---------------------------------------------------------------------------
# Dining tool tests
# ---------------------------------------------------------------------------

def test_get_dining_commons_status_count(seeded_session):
    """Should return 4 commons from fixtures."""
    result = get_dining_commons_status(session=seeded_session)
    assert len(result["commons"]) == 4


def test_get_dining_commons_status_keys(seeded_session):
    """Each commons should have the required keys."""
    result = get_dining_commons_status(session=seeded_session)
    for c in result["commons"]:
        for key in ("commons_code", "commons_name", "has_sack_meal", "has_take_out_meal"):
            assert key in c


def test_get_dining_menu_today(seeded_session):
    """get_dining_menu for today should return fixture items."""
    today_str = date.today().isoformat()
    result = get_dining_menu(date=today_str, session=seeded_session)
    assert result["total_items"] >= 1


def test_get_dining_menu_location_filter(seeded_session):
    """Location filter should narrow results to the matching commons only."""
    today_str = date.today().isoformat()
    result = get_dining_menu(location="Carrillo", date=today_str, session=seeded_session)
    for commons_name in result["by_commons"]:
        assert "carrillo" in commons_name.lower() or "carrillo" in commons_name.lower()


# ---------------------------------------------------------------------------
# Academics tool tests
# ---------------------------------------------------------------------------

def test_get_upcoming_academic_dates(seeded_session):
    """get_upcoming_academic_dates should return ucsb_api events."""
    result = get_upcoming_academic_dates(days=14, session=seeded_session)
    assert "dates" in result
    assert result["count"] >= 1
    assert all(d["category"] is not None for d in result["dates"])
