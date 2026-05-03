"""Source model – tracks configured data sources."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Source(SQLModel, table=True):
    __tablename__ = "source"

    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str = Field(index=True)          # canvas_ics | ucsb_api
    name: str
    config_json: str = Field(default="{}")  # JSON-encoded config blob
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
