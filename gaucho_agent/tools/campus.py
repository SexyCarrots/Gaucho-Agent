"""Tools: live library and gym occupancy (fetched in real-time, not from DB)."""

from __future__ import annotations

import asyncio


def get_library_busyness() -> dict:
    """Return real-time busyness for each UCSB Library section (Waitz data).

    Data refreshes every ~3 minutes. busyness is 0-100 (percent of capacity).
    """
    from gaucho_agent.clients.campus_live import fetch_library_busyness

    locations = asyncio.run(fetch_library_busyness())
    open_locs = [l for l in locations if l["is_open"]]
    closed_locs = [l for l in locations if not l["is_open"]]

    return {
        "source": "Waitz (waitz.io/ucsb)",
        "open_sections": open_locs,
        "closed_sections": closed_locs,
        "total_sections": len(locations),
        "note": "busyness is 0-100 percent of section capacity",
    }


def get_gym_busyness() -> dict:
    """Return real-time occupancy for UCSB Recreation facilities (GoBoard data).

    Data reflects manual counts updated throughout the day. percent is 0-100.
    """
    from gaucho_agent.clients.campus_live import fetch_gym_livecount

    locations = asyncio.run(fetch_gym_livecount())
    open_locs = [l for l in locations if not l["is_closed"]]
    closed_locs = [l for l in locations if l["is_closed"]]

    # Group open locations by facility area
    by_facility: dict[str, list] = {}
    for loc in open_locs:
        by_facility.setdefault(loc["facility"], []).append(loc)

    return {
        "source": "UCSB Recreation (recreation.ucsb.edu/facilities/livecount)",
        "by_facility": by_facility,
        "closed_locations": closed_locs,
        "total_locations": len(locations),
        "note": "percent is current occupancy as % of capacity",
    }
