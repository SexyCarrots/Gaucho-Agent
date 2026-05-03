"""Dining sync service – commons open/closed status and menus."""

from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Session, delete, select

from gaucho_agent.clients.ucsb_api import UCSBClient
from gaucho_agent.config import settings
from gaucho_agent.models.dining import DiningCommonsStatus, DiningMenuItem
from gaucho_agent.models.sync_run import SyncRun
from gaucho_agent.utils.time import today_local


async def sync_dining(session: Session) -> SyncRun:
    """Sync dining commons open/closed status and today's menu items."""
    run = SyncRun(source_kind="ucsb_dining", started_at=datetime.utcnow())
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
    today = today_local()
    today_str = today.strftime("%Y-%m-%d")
    upserted = 0

    try:
        # 1. Static commons list (code, name, location, amenities)
        all_commons = await client.get_dining_commons()
        all_codes = {c["code"]: c for c in all_commons if "code" in c}

        # 2. Which commons are open today (absent = closed)
        open_today = await client.get_open_commons(today_str)
        open_codes = {c["code"] for c in open_today if "code" in c}

        # 3. Upsert DiningCommonsStatus for every known commons
        for code, info in all_codes.items():
            existing = session.exec(
                select(DiningCommonsStatus).where(DiningCommonsStatus.commons_code == code)
            ).first()
            location = info.get("location") or {}
            now = datetime.utcnow()
            is_open = code in open_codes

            if existing:
                existing.commons_name = info.get("name", code)
                existing.has_sack_meal = info.get("hasSackMeal", False)
                existing.has_take_out_meal = info.get("hasTakeOutMeal", False)
                existing.has_dining_cam = info.get("hasDiningCam", False)
                existing.location_lat = location.get("latitude")
                existing.location_lng = location.get("longitude")
                existing.is_open_today = is_open
                existing.status_date = today
                existing.raw_json = json.dumps(info)
                existing.updated_at = now
                session.add(existing)
            else:
                session.add(DiningCommonsStatus(
                    commons_code=code,
                    commons_name=info.get("name", code),
                    has_sack_meal=info.get("hasSackMeal", False),
                    has_take_out_meal=info.get("hasTakeOutMeal", False),
                    has_dining_cam=info.get("hasDiningCam", False),
                    location_lat=location.get("latitude"),
                    location_lng=location.get("longitude"),
                    is_open_today=is_open,
                    status_date=today,
                    raw_json=json.dumps(info),
                    updated_at=now,
                ))
            upserted += 1

        session.commit()

        # 4. Clear stale menu items for today, then insert fresh ones
        session.exec(delete(DiningMenuItem).where(DiningMenuItem.menu_date == today))
        session.commit()

        # 5. For each open commons, walk meal periods → items
        for commons_info in open_today:
            code = commons_info.get("code", "")
            name = commons_info.get("name") or all_codes.get(code, {}).get("name", code)

            meal_periods = await client.get_meal_periods(today_str, code)
            for period in meal_periods:
                meal_code = period.get("code", "")
                meal_name = period.get("name", meal_code)

                items = await client.get_meal_items(today_str, code, meal_code)
                for item in items:
                    session.add(DiningMenuItem(
                        commons_code=code,
                        commons_name=name,
                        meal_code=meal_code,
                        name=item.get("name", ""),
                        station_name=item.get("station"),
                        menu_date=today,
                        updated_at=datetime.utcnow(),
                    ))
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
