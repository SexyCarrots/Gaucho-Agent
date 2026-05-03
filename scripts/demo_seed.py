#!/usr/bin/env python3
"""Demo seed script – seeds the local DB from fixture files for demo purposes."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Allow running directly: python scripts/demo_seed.py
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table

from gaucho_agent.clients.canvas_ics import normalize_canvas_event, parse_ics
from gaucho_agent.db import get_session, init_db
from gaucho_agent.models.dining import DiningCommonsStatus, DiningMenuItem
from gaucho_agent.models.event import Event
from sqlmodel import select

console = Console()
FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures"


def seed_canvas_events(session) -> int:
    """Seed canvas events from sample.ics fixture."""
    ics_path = FIXTURES / "sample.ics"
    if not ics_path.exists():
        console.print(f"[red]Missing fixture:[/] {ics_path}")
        return 0

    events = parse_ics(ics_path.read_text())
    count = 0
    now_dt = datetime.now(tz=timezone.utc)

    # Shift events to be relative to now so they appear "upcoming"
    base_offset = timedelta(days=3)

    for i, evt in enumerate(events):
        upsert = normalize_canvas_event(evt)

        # Shift timestamps to make them upcoming from today
        if upsert.start_at:
            upsert.start_at = now_dt + base_offset + timedelta(days=i)
            if upsert.end_at:
                upsert.end_at = upsert.start_at + timedelta(hours=1)

        existing = session.exec(
            select(Event).where(Event.external_id == upsert.external_id)
        ).first()

        ts = datetime.utcnow()
        if existing:
            existing.title = upsert.title
            existing.start_at = upsert.start_at
            existing.end_at = upsert.end_at
            existing.updated_at = ts
            session.add(existing)
        else:
            session.add(
                Event(
                    source_kind=upsert.source_kind,
                    external_id=upsert.external_id,
                    title=upsert.title,
                    category=upsert.category,
                    course_code=upsert.course_code,
                    start_at=upsert.start_at,
                    end_at=upsert.end_at,
                    all_day=upsert.all_day,
                    description=upsert.description,
                    url=upsert.url,
                    created_at=ts,
                    updated_at=ts,
                )
            )
        count += 1

    session.commit()
    return count


def seed_dining_commons(session) -> int:
    """Seed dining commons from fixture."""
    fixture = FIXTURES / "ucsb" / "dining_commons.json"
    if not fixture.exists():
        console.print(f"[red]Missing fixture:[/] {fixture}")
        return 0

    data = json.loads(fixture.read_text())
    count = 0
    for item in data:
        code = item.get("code", "").strip()
        name = item.get("name", code)
        location = item.get("location") or {}

        existing = session.exec(
            select(DiningCommonsStatus).where(DiningCommonsStatus.commons_code == code)
        ).first()

        ts = datetime.utcnow()
        if existing:
            existing.commons_name = name
            existing.updated_at = ts
            session.add(existing)
        else:
            session.add(
                DiningCommonsStatus(
                    commons_code=code,
                    commons_name=name,
                    has_sack_meal=item.get("hasSackMeal", False),
                    has_take_out_meal=item.get("hasTakeOutMeal", False),
                    has_dining_cam=item.get("hasDiningCam", False),
                    location_lat=location.get("latitude"),
                    location_lng=location.get("longitude"),
                    raw_json=json.dumps(item),
                    updated_at=ts,
                )
            )
        count += 1

    session.commit()
    return count


def seed_dining_menu(session) -> int:
    """Seed today's dining menu from fixture."""
    fixture = FIXTURES / "ucsb" / "dining_menu.json"
    if not fixture.exists():
        console.print(f"[red]Missing fixture:[/] {fixture}")
        return 0

    data = json.loads(fixture.read_text())
    today = date.today()
    count = 0

    for item in data:
        session.add(
            DiningMenuItem(
                commons_code=item.get("diningCommonCode", "").strip(),
                commons_name=item.get("diningCommonName", ""),
                meal_code=item.get("mealCode", ""),
                name=item.get("itemName", ""),
                station_name=item.get("stationName"),
                menu_date=today,
                dietary_info=json.dumps(item.get("dietaryOptions") or []),
                raw_json=json.dumps(item),
                updated_at=datetime.utcnow(),
            )
        )
        count += 1

    session.commit()
    return count


def seed_academic_events(session) -> int:
    """Seed academic events from fixture."""
    fixture = FIXTURES / "ucsb" / "events.json"
    quarter_fixture = FIXTURES / "ucsb" / "quarter_calendar.json"
    count = 0
    now = datetime.utcnow()

    if fixture.exists():
        events_data = json.loads(fixture.read_text())
        for e in events_data:
            eid = f"ucsb_event_{e.get('id', id(e))}"
            existing = session.exec(
                select(Event).where(Event.external_id == eid)
            ).first()

            # Parse start date and shift to upcoming
            start_str = e.get("startDate") or ""
            try:
                start_dt = datetime.strptime(start_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                # Shift to be upcoming from now
                start_dt = datetime.now(tz=timezone.utc) + timedelta(days=8)
            except ValueError:
                start_dt = None

            if existing:
                existing.updated_at = now
                session.add(existing)
            else:
                session.add(
                    Event(
                        source_kind="ucsb_api",
                        external_id=eid,
                        title=e.get("title", ""),
                        category="event",
                        description=e.get("description"),
                        location=e.get("location"),
                        start_at=start_dt,
                        url=e.get("url"),
                        created_at=now,
                        updated_at=now,
                    )
                )
            count += 1

    if quarter_fixture.exists():
        quarters = json.loads(quarter_fixture.read_text())
        for q in quarters:
            qname = q.get("quarter", "")
            dates = {
                "firstDay": q.get("firstDayOfClasses", ""),
                "lastDay": q.get("lastDayOfClasses", ""),
                "firstFinal": q.get("firstDayOfFinals", ""),
                "lastFinal": q.get("lastDayOfFinals", ""),
            }
            for label, date_str in dates.items():
                if not date_str:
                    continue
                eid = f"ucsb_quarter_{qname}_{label}"
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    dt = None
                existing = session.exec(
                    select(Event).where(Event.external_id == eid)
                ).first()
                if not existing:
                    session.add(
                        Event(
                            source_kind="ucsb_api",
                            external_id=eid,
                            title=f"{qname} – {label}",
                            category="academic",
                            start_at=dt,
                            end_at=dt,
                            all_day=True,
                            raw_json=json.dumps(q),
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    count += 1

    session.commit()
    return count


def print_summary(session) -> None:
    """Print a summary of seeded data."""
    from sqlmodel import func

    events = session.exec(select(Event)).all()
    commons = session.exec(select(DiningCommonsStatus)).all()
    menu_items = session.exec(select(DiningMenuItem)).all()

    console.print("\n[bold cyan]Seeded Data Summary[/]")

    t = Table(show_header=True, header_style="bold magenta")
    t.add_column("Category")
    t.add_column("Count", justify="right")

    canvas_events = [e for e in events if e.source_kind == "canvas_ics"]
    ucsb_events = [e for e in events if e.source_kind == "ucsb_api"]

    t.add_row("Canvas Events", str(len(canvas_events)))
    t.add_row("UCSB Academic/Events", str(len(ucsb_events)))
    t.add_row("Dining Commons", str(len(commons)))
    t.add_row("Dining Menu Items", str(len(menu_items)))
    console.print(t)

    if canvas_events:
        console.print("\n[bold]Canvas Events:[/]")
        for e in canvas_events:
            console.print(f"  [{e.category}] {e.title} – {e.course_code or 'N/A'} – {e.start_at}")


def main() -> None:
    console.print(Panel := None)
    console.rule("[bold cyan]Gaucho-Agent Demo Seed[/]")

    console.print("[dim]Initializing database...[/]")
    init_db()

    with get_session() as session:
        console.print("[dim]Seeding Canvas events...[/]")
        n = seed_canvas_events(session)
        console.print(f"  [green]✓[/] {n} Canvas events seeded")

        console.print("[dim]Seeding dining commons...[/]")
        n = seed_dining_commons(session)
        console.print(f"  [green]✓[/] {n} dining commons seeded")

        console.print("[dim]Seeding dining menu...[/]")
        n = seed_dining_menu(session)
        console.print(f"  [green]✓[/] {n} menu items seeded")

        console.print("[dim]Seeding academic events...[/]")
        n = seed_academic_events(session)
        console.print(f"  [green]✓[/] {n} academic records seeded")

        print_summary(session)

    console.print("\n[bold green]Demo seed complete![/]")
    console.print("Try: [cyan]gaucho upcoming[/] or [cyan]gaucho plan[/] or [cyan]gaucho dining[/]")


if __name__ == "__main__":
    main()
