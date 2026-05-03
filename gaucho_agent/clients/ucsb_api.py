"""UCSB API client with retry logic."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from gaucho_agent.config import settings

UCSB_EVENTS_URL = "https://www.campuscalendar.ucsb.edu/api/2/events"


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, (httpx.TimeoutException, httpx.ConnectError))


class UCSBClient:
    """Async client for the UCSB Developer API."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "ucsb-api-key": self._api_key,
            "Accept": "application/json",
            "User-Agent": settings.sync_user_agent,
        }

    def _public_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "User-Agent": settings.sync_user_agent,
        }

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict | list:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers(), params=params or {})
            response.raise_for_status()
            return response.json()

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def get_public_url(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict | list:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._public_headers(), params=params or {})
            response.raise_for_status()
            return response.json()

    async def get_dining_commons(self) -> list:
        result = await self.get("/dining/commons/v1")
        return result if isinstance(result, list) else []

    async def get_open_commons(self, date: str) -> list:
        """Return commons codes that are open on date (YYYY-MM-DD).
        A commons absent from this list is closed for that day."""
        result = await self.get(f"/dining/menu/v1/{date}")
        return result if isinstance(result, list) else []

    async def get_meal_periods(self, date: str, commons_code: str) -> list:
        """Return meal periods (brunch, dinner, …) for a commons on date."""
        result = await self.get(f"/dining/menu/v1/{date}/{commons_code}")
        return result if isinstance(result, list) else []

    async def get_meal_items(self, date: str, commons_code: str, meal_code: str) -> list:
        """Return menu items [{name, station}] for one meal at one commons."""
        result = await self.get(f"/dining/menu/v1/{date}/{commons_code}/{meal_code}")
        return result if isinstance(result, list) else []

    async def get_academic_quarter_calendar(self, quarter: str | None = None) -> list:
        """Return UCSB quarter calendar entries.

        The quarter calendar API exposes quarters as hierarchical resources
        under /quarters; it does not accept a quarter query parameter.
        """
        if quarter and quarter.lower() == "current":
            result = await self.get("/academics/quartercalendar/v1/quarters/current")
            if isinstance(result, dict):
                return [result]
            return result if isinstance(result, list) else []

        result = await self.get("/academics/quartercalendar/v1/quarters")
        quarters = result if isinstance(result, list) else []
        if not quarter:
            return quarters

        quarter_code = quarter.lower()
        return [
            item
            for item in quarters
            if str(item.get("quarter") or item.get("quarterCode") or "").lower() == quarter_code
        ]

    async def get_events(self) -> list:
        events: list[dict[str, Any]] = []
        page = 1
        total_pages = 1

        while page <= total_pages:
            result = await self.get_public_url(UCSB_EVENTS_URL, params={"page": page})
            if not isinstance(result, dict):
                return result if isinstance(result, list) else events

            page_data = result.get("page") or {}
            total_pages = int(page_data.get("total") or total_pages)
            for item in result.get("events") or []:
                if isinstance(item, dict) and isinstance(item.get("event"), dict):
                    events.append(item["event"])
                elif isinstance(item, dict):
                    events.append(item)
            page += 1

        return events

    async def get_curriculums(
        self,
        quarter: str | None = None,
        department: str | None = None,
    ) -> list:
        params: dict[str, str] = {}
        if quarter:
            params["quarter"] = quarter
        if department:
            params["deptCode"] = department
        result = await self.get("/academics/curriculums/v1", params=params)
        return result if isinstance(result, list) else []

    async def get_department_chairs(self) -> list:
        result = await self.get("/academics/departmentchairs/v1")
        return result if isinstance(result, list) else []

    async def get_student_record_code_lookups(self) -> list:
        result = await self.get("/students/lookups/v1")
        return result if isinstance(result, list) else []
