"""Tests for UCSB academics sync normalization."""

from __future__ import annotations

from datetime import datetime

from gaucho_agent.services.sync_academics import (
    _campus_event_all_day,
    _campus_event_description,
    _campus_event_end,
    _campus_event_external_id,
    _campus_event_location,
    _campus_event_start,
    _parse_iso,
    _quarter_milestones,
)


def test_parse_iso_handles_ucsb_datetime_as_local_time():
    """UCSB timestamps are local campus time and should be stored as UTC."""
    assert _parse_iso("2026-05-11T09:00:00") == datetime(2026, 5, 11, 16, 0)


def test_quarter_milestones_include_finals_and_pass_dates():
    quarter = {
        "quarter": "20264",
        "qyy": "F26",
        "name": "FALL 2026",
        "firstDayOfClasses": "2026-09-24T00:00:00",
        "lastDayOfClasses": "2026-12-04T00:00:00",
        "firstDayOfFinals": "2026-12-05T00:00:00",
        "lastDayOfFinals": "2026-12-11T00:00:00",
        "lastDayOfSchedule": "2027-01-03T00:00:00",
        "pass1Begin": "2026-05-11T09:00:00",
        "pass2Begin": "2026-05-18T09:00:00",
        "pass3Begin": "2026-09-08T09:00:00",
    }

    milestones = _quarter_milestones(quarter)
    titles = {m["title"]: m for m in milestones}

    assert "FALL 2026 - Finals Week" in titles
    assert titles["FALL 2026 - Pass 1 Begins"]["start_at"] == datetime(2026, 5, 11, 16, 0)
    assert titles["FALL 2026 - Schedule Ends (Quarter End)"]["all_day"] is True


def test_localist_campus_event_fields_are_normalized():
    event = {
        "id": 123,
        "title": "Library Exhibit",
        "description": "<p>Open to campus.</p>",
        "location_name": "Library",
        "room_number": "Special Research Collections",
        "url": "https://example.edu/event",
        "event_instances": [
            {
                "event_instance": {
                    "id": 456,
                    "start": "2026-05-02T10:00:00-07:00",
                    "end": "2026-05-02T11:30:00-07:00",
                    "all_day": False,
                }
            }
        ],
    }

    assert _campus_event_external_id(event) == "ucsb_event_123_456"
    assert _campus_event_start(event) == datetime(2026, 5, 2, 17, 0)
    assert _campus_event_end(event) == datetime(2026, 5, 2, 18, 30)
    assert _campus_event_all_day(event) is False
    assert _campus_event_description(event) == "Open to campus."
    assert _campus_event_location(event) == "Library, Special Research Collections"
