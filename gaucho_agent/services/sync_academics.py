"""Academics sync service - quarter calendar and campus events."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlmodel import Session, select

from gaucho_agent.clients.ucsb_api import UCSBClient
from gaucho_agent.config import settings
from gaucho_agent.models.event import Event
from gaucho_agent.models.sync_run import SyncRun
from gaucho_agent.utils.parsing import strip_html

logger = logging.getLogger(__name__)


def _parse_iso(value: str | None) -> datetime | None:
    """Parse a UCSB local ISO date/datetime into naive UTC for SQLite."""
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            dt = datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(settings.local_timezone))
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _is_all_day(value: str | None) -> bool:
    """Treat date-only or local-midnight UCSB timestamps as all-day milestones."""
    if not value:
        return True
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return len(value) <= 10
    return dt.hour == 0 and dt.minute == 0 and dt.second == 0


def _quarter_display_name(q: dict[str, Any]) -> str:
    return str(q.get("name") or q.get("qyy") or q.get("quarter") or "Quarter")


def _quarter_external_id(q: dict[str, Any]) -> str:
    return str(q.get("quarter") or q.get("qyy") or q.get("name") or id(q))


def _quarter_milestones(q: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize UCSB quarter fields into user-facing academic events."""
    name = _quarter_display_name(q)
    quarter_id = _quarter_external_id(q)
    fields = [
        ("firstDayOfQuarter", "firstDayOfQuarter", "First Day of Quarter"),
        ("firstDayOfClasses", "firstDay", "First Day of Classes"),
        ("lastDayOfClasses", "lastDay", "Last Day of Classes"),
        ("firstDayOfFinals", "firstFinal", "First Day of Finals"),
        ("lastDayOfFinals", "lastFinal", "Last Day of Finals"),
        ("lastDayOfSchedule", "scheduleEnd", "Schedule Ends (Quarter End)"),
        ("pass1Begin", "pass1Begin", "Pass 1 Begins"),
        ("pass2Begin", "pass2Begin", "Pass 2 Begins"),
        ("pass3Begin", "pass3Begin", "Pass 3 Begins"),
        ("feeDeadline", "feeDeadline", "Fee Deadline"),
        ("lastDayToAddUnderGrad", "lastDayToAddUnderGrad", "Last Day To Add - Undergraduate"),
        ("lastDayToAddGrad", "lastDayToAddGrad", "Last Day To Add - Graduate"),
        ("lastDayThirdWeek", "lastDayThirdWeek", "Last Day of Third Week"),
    ]

    events: list[dict[str, Any]] = []
    for field, slug, label in fields:
        date_str = q.get(field)
        start_at = _parse_iso(date_str)
        if not start_at:
            continue
        events.append(
            {
                "external_id": f"ucsb_quarter_{quarter_id}_{slug}",
                "title": f"{name} - {label}",
                "start_at": start_at,
                "end_at": start_at,
                "all_day": _is_all_day(date_str),
                "raw_json": json.dumps(q),
            }
        )

    first_final = _parse_iso(q.get("firstDayOfFinals"))
    last_final = _parse_iso(q.get("lastDayOfFinals"))
    if first_final and last_final:
        events.append(
            {
                "external_id": f"ucsb_quarter_{quarter_id}_finalsWeek",
                "title": f"{name} - Finals Week",
                "start_at": first_final,
                "end_at": last_final,
                "all_day": True,
                "raw_json": json.dumps(q),
            }
        )

    return events


def _campus_event_instance(event: dict[str, Any]) -> dict[str, Any]:
    instances = event.get("event_instances") or []
    if not instances:
        return {}
    first = instances[0]
    if isinstance(first, dict) and isinstance(first.get("event_instance"), dict):
        return first["event_instance"]
    return first if isinstance(first, dict) else {}


def _campus_event_external_id(event: dict[str, Any]) -> str:
    instance = _campus_event_instance(event)
    event_id = event.get("id") or event.get("eventId") or id(event)
    instance_id = instance.get("id")
    if instance_id:
        return f"ucsb_event_{event_id}_{instance_id}"
    return f"ucsb_event_{event_id}"


def _campus_event_location(event: dict[str, Any]) -> str | None:
    parts = [
        event.get("location_name"),
        event.get("room_number"),
        event.get("location"),
    ]
    location = ", ".join(str(part) for part in parts if part)
    return location or None


def _campus_event_description(event: dict[str, Any]) -> str | None:
    description = event.get("description_text") or event.get("description")
    if not description:
        return None
    return strip_html(str(description))


def _campus_event_start(event: dict[str, Any]) -> datetime | None:
    instance = _campus_event_instance(event)
    return _parse_iso(
        event.get("startDate")
        or event.get("startTime")
        or instance.get("start")
        or event.get("first_date")
    )


def _campus_event_end(event: dict[str, Any]) -> datetime | None:
    instance = _campus_event_instance(event)
    return _parse_iso(
        event.get("endDate")
        or event.get("endTime")
        or instance.get("end")
        or event.get("last_date")
    )


def _campus_event_all_day(event: dict[str, Any]) -> bool:
    instance = _campus_event_instance(event)
    if "all_day" in instance:
        return bool(instance["all_day"])
    return _is_all_day(event.get("startDate") or event.get("startTime") or event.get("first_date"))


def _upsert_event(session: Session, external_id: str, data: dict[str, Any]) -> bool:
    """Upsert an event; return True if a new row was created."""
    existing = session.exec(
        select(Event).where(Event.external_id == external_id)
    ).first()
    now = datetime.utcnow()
    if existing:
        for k, v in data.items():
            setattr(existing, k, v)
        existing.updated_at = now
        session.add(existing)
        return False
    else:
        session.add(Event(external_id=external_id, created_at=now, updated_at=now, **data))
        return True


async def sync_academics(session: Session) -> SyncRun:
    """Fetch quarter calendar and campus events."""
    run = SyncRun(source_kind="ucsb_academics", started_at=datetime.utcnow())
    session.add(run)
    session.commit()
    session.refresh(run)

    if not settings.ucsb_api_key:
        run.finished_at = datetime.utcnow()
        run.success = False
        run.error_text = "UCSB_API_KEY is not configured."
        session.add(run)
        session.commit()
        return run

    client = UCSBClient(api_key=settings.ucsb_api_key, base_url=settings.ucsb_api_base)
    upserted = 0
    skipped: list[str] = []

    # --- Quarter Calendar ---
    try:
        quarters = await client.get_academic_quarter_calendar()
        for q in quarters:
            for event in _quarter_milestones(q):
                _upsert_event(
                    session,
                    event["external_id"],
                    {
                        "source_kind": "ucsb_api",
                        "title": event["title"],
                        "category": "academic",
                        "start_at": event["start_at"],
                        "end_at": event["end_at"],
                        "all_day": event["all_day"],
                        "raw_json": event["raw_json"],
                    },
                )
                upserted += 1
        session.commit()
    except httpx.HTTPStatusError as exc:
        logger.warning("Quarter calendar skipped: %s", exc)
        skipped.append(f"quarter_calendar ({exc.response.status_code})")
    except Exception as exc:
        logger.warning("Quarter calendar skipped: %s", exc)
        skipped.append(f"quarter_calendar ({exc!r})")

    # --- Campus Events ---
    try:
        events = await client.get_events()
        for e in events:
            eid = _campus_event_external_id(e)
            _upsert_event(
                session,
                eid,
                {
                    "source_kind": "ucsb_api",
                    "title": e.get("title") or e.get("eventTitle") or "",
                    "category": "event",
                    "description": _campus_event_description(e),
                    "location": _campus_event_location(e),
                    "start_at": _campus_event_start(e),
                    "end_at": _campus_event_end(e),
                    "all_day": _campus_event_all_day(e),
                    "url": e.get("url"),
                    "raw_json": json.dumps(e),
                },
            )
            upserted += 1
        session.commit()
    except httpx.HTTPStatusError as exc:
        logger.warning("Campus events skipped: %s", exc)
        skipped.append(f"events ({exc.response.status_code})")
    except Exception as exc:
        logger.warning("Campus events skipped: %s", exc)
        skipped.append(f"events ({exc!r})")

    run.finished_at = datetime.utcnow()
    run.success = True
    run.records_upserted = upserted
    if skipped:
        run.error_text = "Skipped (check API approval): " + ", ".join(skipped)

    session.add(run)
    session.commit()
    return run
