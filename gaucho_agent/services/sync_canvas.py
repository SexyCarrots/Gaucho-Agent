"""Canvas ICS sync service."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from gaucho_agent.clients.canvas_ics import fetch_ics, normalize_canvas_event, parse_ics
from gaucho_agent.config import settings
from gaucho_agent.models.event import Event
from gaucho_agent.models.sync_run import SyncRun


async def sync_canvas(session: Session) -> SyncRun:
    """Fetch Canvas ICS feed and upsert events into DB."""
    run = SyncRun(source_kind="canvas_ics", started_at=datetime.utcnow())
    session.add(run)
    session.commit()
    session.refresh(run)

    if not settings.canvas_ics_url:
        run.finished_at = datetime.utcnow()
        run.success = False
        run.error_text = "CANVAS_ICS_URL is not configured."
        session.add(run)
        session.commit()
        return run

    try:
        raw = await fetch_ics(settings.canvas_ics_url)
        events = parse_ics(raw)
        upserted = 0

        for canvas_evt in events:
            upsert = normalize_canvas_event(canvas_evt)
            existing = session.exec(
                select(Event).where(Event.external_id == upsert.external_id)
            ).first()

            now = datetime.utcnow()
            if existing:
                existing.title = upsert.title
                existing.category = upsert.category
                existing.course_code = upsert.course_code
                existing.course_name = upsert.course_name
                existing.start_at = upsert.start_at
                existing.end_at = upsert.end_at
                existing.all_day = upsert.all_day
                existing.description = upsert.description
                existing.url = upsert.url
                existing.updated_at = now
                session.add(existing)
            else:
                new_evt = Event(
                    source_kind=upsert.source_kind,
                    external_id=upsert.external_id,
                    title=upsert.title,
                    category=upsert.category,
                    course_code=upsert.course_code,
                    course_name=upsert.course_name,
                    start_at=upsert.start_at,
                    end_at=upsert.end_at,
                    all_day=upsert.all_day,
                    description=upsert.description,
                    url=upsert.url,
                    created_at=now,
                    updated_at=now,
                )
                session.add(new_evt)
            upserted += 1

        session.commit()
        run.finished_at = datetime.utcnow()
        run.success = True
        run.records_upserted = upserted
    except Exception as exc:
        run.finished_at = datetime.utcnow()
        run.success = False
        run.error_text = str(exc)

    session.add(run)
    session.commit()
    return run
