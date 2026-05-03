"""Tests for Canvas ICS parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from gaucho_agent.clients.canvas_ics import normalize_canvas_event, parse_ics
from gaucho_agent.utils.parsing import extract_course_code

FIXTURE = Path(__file__).parent / "fixtures" / "sample.ics"


@pytest.fixture
def ics_text() -> str:
    return FIXTURE.read_text()


@pytest.fixture
def parsed_events(ics_text: str):
    return parse_ics(ics_text)


def test_parse_ics_count(parsed_events):
    """Exactly 5 events should be parsed from sample.ics."""
    assert len(parsed_events) == 5


def test_uids_extracted(parsed_events):
    """Every parsed event should have a non-empty UID."""
    uids = [e.uid for e in parsed_events]
    assert all(uid for uid in uids)
    # UIDs should be unique
    assert len(set(uids)) == 5


def test_all_day_detection(parsed_events):
    """The Memorial Day event should be detected as all-day."""
    all_day_events = [e for e in parsed_events if e.all_day]
    assert len(all_day_events) == 1
    assert "Memorial Day" in all_day_events[0].summary


def test_timed_events_not_all_day(parsed_events):
    """Timed events should not be flagged as all-day."""
    timed = [e for e in parsed_events if not e.all_day]
    assert len(timed) == 4


def test_course_code_extraction_from_summary():
    """extract_course_code should parse [CMPSC 291A S26] correctly."""
    result = extract_course_code("Homework 3 [CMPSC 291A S26]")
    assert result is not None
    code, quarter = result
    assert code == "CMPSC 291A"
    assert quarter == "S26"


def test_course_code_extraction_missing():
    """extract_course_code returns None when no pattern is present."""
    assert extract_course_code("No Classes – Memorial Day") is None


def test_normalize_strips_course_bracket(parsed_events):
    """normalize_canvas_event should strip [CMPSC 291A S26] from the title."""
    hw3 = next(e for e in parsed_events if "Homework 3" in e.summary)
    upsert = normalize_canvas_event(hw3)
    assert "[" not in upsert.title
    assert upsert.course_code == "CMPSC 291A"


def test_normalize_html_stripped(parsed_events):
    """normalize_canvas_event should strip HTML from description."""
    proposal = next(e for e in parsed_events if "Proposal" in e.summary)
    upsert = normalize_canvas_event(proposal)
    assert "<p>" not in (upsert.description or "")
    assert "Gradescope" in (upsert.description or "")


def test_lecture_category(parsed_events):
    """Events with 'Lecture' in the title should have category='class'."""
    lecture = next(e for e in parsed_events if "Lecture" in e.summary)
    upsert = normalize_canvas_event(lecture)
    assert upsert.category == "class"


def test_assignment_category(parsed_events):
    """Regular assignment events should have category='assignment'."""
    hw3 = next(e for e in parsed_events if "Homework 3" in e.summary)
    upsert = normalize_canvas_event(hw3)
    assert upsert.category == "assignment"
