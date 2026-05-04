"""Live campus occupancy clients — library (Waitz) and gym (GoBoard/Recreation)."""

from __future__ import annotations

from typing import Any

import httpx

from gaucho_agent.config import settings

WAITZ_URL = "https://waitz.io/live/ucsb"
GOBOARD_URL = (
    "https://goboardapi.azurewebsites.net/api/FacilityCount/GetCountsByAccount"
    "?AccountAPIKey=9ff6a29d-9ef2-4d75-97ea-187f31ac0025"
)

_HEADERS = {
    "Accept": "application/json",
    "User-Agent": settings.sync_user_agent,
}


async def fetch_library_busyness() -> list[dict[str, Any]]:
    """Return live busyness data for UCSB Library sections from Waitz.

    Each item: {name, busyness (0-100), people, capacity, is_open}
    Updates every ~3 minutes.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(WAITZ_URL, headers=_HEADERS)
        resp.raise_for_status()
        payload = resp.json()

    locations = []
    for loc in payload.get("data") or []:
        locations.append({
            "name": loc.get("name", ""),
            "busyness": loc.get("busyness", 0),
            "people": loc.get("people"),
            "capacity": loc.get("capacity"),
            "is_open": loc.get("isOpen", False),
            "is_available": loc.get("isAvailable", False),
            "hour_summary": loc.get("hourSummary", ""),
        })

    return locations


async def fetch_gym_livecount() -> list[dict[str, Any]]:
    """Return live occupancy for UCSB Recreation facilities from GoBoard.

    Each item: {name, facility, count, capacity, percent (0-100), is_closed, updated_at}
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(GOBOARD_URL, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()

    locations = []
    for loc in data if isinstance(data, list) else []:
        count = loc.get("LastCount") or 0
        capacity = loc.get("TotalCapacity") or 0
        percent = round(count / capacity * 100) if capacity > 0 else 0
        locations.append({
            "name": loc.get("LocationName", ""),
            "facility": loc.get("FacilityName", ""),
            "count": count,
            "capacity": capacity,
            "percent": percent,
            "is_closed": loc.get("IsClosed", False),
            "updated_at": loc.get("LastUpdatedDateAndTime", ""),
        })

    return locations
