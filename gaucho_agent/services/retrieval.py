"""Local DB retrieval helpers used by tool functions."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Session, select

from gaucho_agent.models.dining import DiningCommonsStatus, DiningMenuItem
from gaucho_agent.models.event import Event


def get_events_in_range(
    session: Session,
    start: datetime,
    end: datetime,
    source_kind: Optional[str] = None,
    category: Optional[str] = None,
) -> list[Event]:
    """Return events whose start_at falls within [start, end]."""
    stmt = select(Event).where(Event.start_at >= start, Event.start_at <= end)
    if source_kind:
        stmt = stmt.where(Event.source_kind == source_kind)
    if category:
        stmt = stmt.where(Event.category == category)
    stmt = stmt.order_by(Event.start_at)
    return list(session.exec(stmt).all())


def get_dining_menu_for_date(
    session: Session,
    menu_date: date,
    commons_name: Optional[str] = None,
) -> list[DiningMenuItem]:
    """Return menu items for a date, optionally filtered by commons name or code."""
    stmt = select(DiningMenuItem).where(DiningMenuItem.menu_date == menu_date)
    if commons_name:
        stmt = stmt.where(
            DiningMenuItem.commons_name.ilike(f"%{commons_name}%")
            | DiningMenuItem.commons_code.ilike(f"%{commons_name}%")
        )
    stmt = stmt.order_by(DiningMenuItem.commons_code, DiningMenuItem.meal_code)
    return list(session.exec(stmt).all())


def get_dining_status(session: Session) -> list[DiningCommonsStatus]:
    """Return all dining commons status records."""
    stmt = select(DiningCommonsStatus).order_by(DiningCommonsStatus.commons_name)
    return list(session.exec(stmt).all())
