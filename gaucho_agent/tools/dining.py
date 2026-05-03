"""Tools: dining commons open/closed status and menu queries."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from gaucho_agent.services.retrieval import get_dining_menu_for_date, get_dining_status
from gaucho_agent.utils.time import today_local


def get_dining_commons_status(session: Optional[Session] = None) -> dict:
    """Return each dining commons with its open/closed status for today."""
    if session is None:
        from gaucho_agent.db import get_session
        with get_session() as s:
            return get_dining_commons_status(session=s)

    today = today_local()
    commons = get_dining_status(session)
    items = []
    for c in commons:
        # status_date tells us when is_open_today was last evaluated
        status_fresh = c.status_date == today if c.status_date else False
        items.append({
            "commons_code": c.commons_code,
            "commons_name": c.commons_name,
            "is_open_today": c.is_open_today if status_fresh else None,
            "status_date": c.status_date.isoformat() if c.status_date else None,
            "has_sack_meal": c.has_sack_meal,
            "has_take_out_meal": c.has_take_out_meal,
        })

    open_count = sum(1 for i in items if i["is_open_today"] is True)
    return {
        "date": today.isoformat(),
        "commons": items,
        "open_count": open_count,
        "note": "is_open_today=null means dining sync hasn't run yet for today",
    }


def get_dining_menu(
    location: Optional[str] = None,
    date: Optional[str] = None,
    session: Optional[Session] = None,
) -> dict:
    """Return dining menu items for a date and/or commons. location matches commons name."""
    if session is None:
        from gaucho_agent.db import get_session
        with get_session() as s:
            return get_dining_menu(location=location, date=date, session=s)

    from datetime import datetime
    if date:
        try:
            menu_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            menu_date = today_local()
    else:
        menu_date = today_local()

    items_db = get_dining_menu_for_date(session, menu_date, commons_name=location)

    # Group by commons → meal period
    grouped: dict[str, dict[str, list]] = {}
    for m in items_db:
        grouped.setdefault(m.commons_name, {}).setdefault(m.meal_code, []).append({
            "name": m.name,
            "station": m.station_name,
        })

    return {
        "date": menu_date.isoformat(),
        "location_filter": location,
        "by_commons": grouped,
        "total_items": len(items_db),
    }
