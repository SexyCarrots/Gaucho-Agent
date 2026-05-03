"""API routes for status, events, and dining queries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from gaucho_agent.db import get_session as _get_session
from gaucho_agent.models.sync_run import SyncRun
from gaucho_agent.tools.assignments import get_upcoming_assignments
from gaucho_agent.tools.dining import get_dining_commons_status

router = APIRouter(tags=["status"])


def _session():
    with _get_session() as s:
        yield s


@router.get("/status")
def status(session: Session = Depends(_session)):
    """Return last sync run info for each source kind."""
    kinds = ["canvas_ics", "ucsb_dining", "ucsb_academics"]
    result: dict = {}
    for kind in kinds:
        run = session.exec(
            select(SyncRun)
            .where(SyncRun.source_kind == kind)
            .order_by(SyncRun.started_at.desc())
        ).first()
        if run:
            result[kind] = {
                "last_sync": run.started_at.isoformat() if run.started_at else None,
                "success": run.success,
                "records_upserted": run.records_upserted,
                "error": run.error_text,
            }
        else:
            result[kind] = {"last_sync": None}
    return result


@router.get("/events/upcoming")
def events_upcoming(
    days: int = Query(7, ge=1, le=90),
    session: Session = Depends(_session),
):
    """Return upcoming assignments from Canvas feed."""
    return get_upcoming_assignments(days=days, session=session)


@router.get("/dining/status")
def dining_status(session: Session = Depends(_session)):
    """Return dining commons status."""
    return get_dining_commons_status(session=session)
