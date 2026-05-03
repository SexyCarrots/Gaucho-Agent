"""SyncRun model – audit log of sync executions."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class SyncRun(SQLModel, table=True):
    __tablename__ = "sync_run"

    id: Optional[int] = Field(default=None, primary_key=True)
    source_kind: str = Field(index=True)      # canvas_ics | ucsb_dining | ucsb_academics
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    success: bool = False
    records_upserted: int = 0
    error_text: Optional[str] = None
