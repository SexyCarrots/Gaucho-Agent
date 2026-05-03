"""Event model – unified calendar events from Canvas and UCSB APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Event(SQLModel, table=True):
    __tablename__ = "event"

    id: Optional[int] = Field(default=None, primary_key=True)
    source_kind: str = Field(index=True)          # canvas_ics | ucsb_api
    external_id: str = Field(unique=True, index=True)  # UID from ICS / API ID
    title: str
    category: Optional[str] = None                # assignment | class | academic | event
    course_code: Optional[str] = None             # e.g. "CMPSC 291A"
    course_name: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    all_day: bool = False
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    raw_json: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
