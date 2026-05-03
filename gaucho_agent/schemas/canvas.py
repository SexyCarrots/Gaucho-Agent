"""Pydantic schemas for Canvas ICS calendar data."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CanvasCalendarEvent(BaseModel):
    uid: str
    summary: str
    description: Optional[str] = None
    url: Optional[str] = None
    dtstart: Optional[datetime] = None
    dtend: Optional[datetime] = None
    all_day: bool = False


class EventUpsert(BaseModel):
    """Normalized event ready for DB upsert."""

    source_kind: str = "canvas_ics"
    external_id: str
    title: str
    category: Optional[str] = None
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    all_day: bool = False
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    raw_json: Optional[str] = None
