"""API routes for triggering data sync."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from gaucho_agent.db import get_session as _get_session
from gaucho_agent.services.sync_canvas import sync_canvas
from gaucho_agent.services.sync_dining import sync_dining
from gaucho_agent.services.sync_academics import sync_academics

router = APIRouter(prefix="/sync", tags=["sync"])


def _session():
    with _get_session() as s:
        yield s


@router.post("/canvas")
async def sync_canvas_route(session: Session = Depends(_session)):
    """Trigger Canvas ICS sync."""
    run = await sync_canvas(session)
    return {
        "source_kind": run.source_kind,
        "success": run.success,
        "records_upserted": run.records_upserted,
        "error": run.error_text,
        "finished_at": run.finished_at,
    }


@router.post("/dining")
async def sync_dining_route(session: Session = Depends(_session)):
    """Trigger dining data sync."""
    run = await sync_dining(session)
    return {
        "source_kind": run.source_kind,
        "success": run.success,
        "records_upserted": run.records_upserted,
        "error": run.error_text,
        "finished_at": run.finished_at,
    }


@router.post("/academics")
async def sync_academics_route(session: Session = Depends(_session)):
    """Trigger academic calendar sync."""
    run = await sync_academics(session)
    return {
        "source_kind": run.source_kind,
        "success": run.success,
        "records_upserted": run.records_upserted,
        "error": run.error_text,
        "finished_at": run.finished_at,
    }
