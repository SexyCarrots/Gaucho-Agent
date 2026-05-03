"""Tests for UCSB API client."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from gaucho_agent.clients.ucsb_api import UCSBClient

FIXTURES = Path(__file__).parent / "fixtures" / "ucsb"


@pytest.fixture
def client() -> UCSBClient:
    return UCSBClient(api_key="test-key-abc123", base_url="https://api.ucsb.edu")


@pytest.fixture
def dining_commons_fixture() -> list:
    return json.loads((FIXTURES / "dining_commons.json").read_text())


@pytest.fixture
def dining_menu_fixture() -> list:
    return json.loads((FIXTURES / "dining_menu.json").read_text())


@pytest.fixture
def quarter_calendar_fixture() -> list:
    return json.loads((FIXTURES / "quarter_calendar.json").read_text())


@pytest.fixture
def events_fixture() -> list:
    return json.loads((FIXTURES / "events.json").read_text())


def _mock_response(data) -> httpx.Response:
    """Build a fake httpx.Response wrapping JSON data."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = data
    response.raise_for_status = MagicMock()
    return response


@pytest.mark.asyncio
async def test_api_key_header_sent(client: UCSBClient, dining_commons_fixture):
    """UCSBClient must include the ucsb-api-key header in every request."""
    captured_headers: dict = {}

    async def fake_get(url, headers=None, params=None):
        captured_headers.update(headers or {})
        return _mock_response(dining_commons_fixture)

    mock_client = AsyncMock()
    mock_client.get = fake_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("gaucho_agent.clients.ucsb_api.httpx.AsyncClient", return_value=mock_client):
        result = await client.get_dining_commons()

    assert "ucsb-api-key" in captured_headers
    assert captured_headers["ucsb-api-key"] == "test-key-abc123"
    assert len(result) == 4


@pytest.mark.asyncio
async def test_get_dining_commons_calls_correct_path(client: UCSBClient, dining_commons_fixture):
    """get_dining_commons should call /dining/commons/v1."""
    captured_url: list[str] = []

    async def fake_get(url, headers=None, params=None):
        captured_url.append(url)
        return _mock_response(dining_commons_fixture)

    mock_client = AsyncMock()
    mock_client.get = fake_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("gaucho_agent.clients.ucsb_api.httpx.AsyncClient", return_value=mock_client):
        await client.get_dining_commons()

    assert captured_url[0].endswith("/dining/commons/v1")


@pytest.mark.asyncio
async def test_get_dining_menu_passes_params(client: UCSBClient, dining_menu_fixture):
    """get_meal_items should call the correct path-based URL."""
    captured_url: list[str] = []

    async def fake_get(url, headers=None, params=None):
        captured_url.append(url)
        return _mock_response(dining_menu_fixture)

    mock_client = AsyncMock()
    mock_client.get = fake_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("gaucho_agent.clients.ucsb_api.httpx.AsyncClient", return_value=mock_client):
        await client.get_meal_items(date="2026-05-06", commons_code="carrillo", meal_code="dinner")

    assert captured_url[0].endswith("/dining/menu/v1/2026-05-06/carrillo/dinner")


@pytest.mark.asyncio
async def test_get_academic_quarter_calendar(client: UCSBClient, quarter_calendar_fixture):
    """get_academic_quarter_calendar should call the documented /quarters path."""
    captured_url: list[str] = []
    captured_params: list[dict] = []

    async def fake_get(url, headers=None, params=None):
        captured_url.append(url)
        captured_params.append(params or {})
        return _mock_response(quarter_calendar_fixture)

    mock_client = AsyncMock()
    mock_client.get = fake_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("gaucho_agent.clients.ucsb_api.httpx.AsyncClient", return_value=mock_client):
        result = await client.get_academic_quarter_calendar()

    assert captured_url[0].endswith("/academics/quartercalendar/v1/quarters")
    assert captured_params[0] == {}
    assert len(result) == 3


@pytest.mark.asyncio
async def test_get_current_academic_quarter_calendar(client: UCSBClient, quarter_calendar_fixture):
    """quarter='current' should call the documented /quarters/current path."""
    captured_url: list[str] = []

    async def fake_get(url, headers=None, params=None):
        captured_url.append(url)
        return _mock_response(quarter_calendar_fixture[0])

    mock_client = AsyncMock()
    mock_client.get = fake_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("gaucho_agent.clients.ucsb_api.httpx.AsyncClient", return_value=mock_client):
        result = await client.get_academic_quarter_calendar(quarter="current")

    assert captured_url[0].endswith("/academics/quartercalendar/v1/quarters/current")
    assert result == [quarter_calendar_fixture[0]]


@pytest.mark.asyncio
async def test_get_specific_academic_quarter_filters_locally(client: UCSBClient, quarter_calendar_fixture):
    """Specific quarter codes are filtered locally because the API uses nested paths."""
    captured_params: list[dict] = []

    async def fake_get(url, headers=None, params=None):
        captured_params.append(params or {})
        return _mock_response(quarter_calendar_fixture)

    mock_client = AsyncMock()
    mock_client.get = fake_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("gaucho_agent.clients.ucsb_api.httpx.AsyncClient", return_value=mock_client):
        result = await client.get_academic_quarter_calendar(quarter="M26")

    assert captured_params[0] == {}
    assert [item["quarter"] for item in result] == ["M26"]


@pytest.mark.asyncio
async def test_retry_on_500(client: UCSBClient, dining_commons_fixture):
    """UCSBClient should retry on HTTP 500 errors (up to 3 attempts)."""
    call_count = 0

    async def flaky_get(url, headers=None, params=None):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            error_response = MagicMock(spec=httpx.Response)
            error_response.status_code = 500
            raise httpx.HTTPStatusError("Server Error", request=MagicMock(), response=error_response)
        return _mock_response(dining_commons_fixture)

    mock_client = AsyncMock()
    mock_client.get = flaky_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("gaucho_agent.clients.ucsb_api.httpx.AsyncClient", return_value=mock_client):
        result = await client.get_dining_commons()

    assert call_count == 3
    assert len(result) == 4


@pytest.mark.asyncio
async def test_get_events_calls_correct_path(client: UCSBClient, events_fixture):
    """get_events should call the direct Campus Calendar API and unwrap Localist events."""
    captured_url: list[str] = []
    captured_params: list[dict] = []

    async def fake_get(url, headers=None, params=None):
        captured_url.append(url)
        captured_params.append(params or {})
        return _mock_response(
            {
                "events": [{"event": event} for event in events_fixture],
                "page": {"current": 1, "size": 10, "total": 1},
            }
        )

    mock_client = AsyncMock()
    mock_client.get = fake_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("gaucho_agent.clients.ucsb_api.httpx.AsyncClient", return_value=mock_client):
        result = await client.get_events()

    assert captured_url[0] == "https://www.campuscalendar.ucsb.edu/api/2/events"
    assert captured_params[0] == {"page": 1}
    assert len(result) == 3


@pytest.mark.asyncio
async def test_get_events_paginates_localist_response(client: UCSBClient, events_fixture):
    """get_events should collect all Localist pages."""
    captured_params: list[dict] = []

    async def fake_get(url, headers=None, params=None):
        captured_params.append(params or {})
        page = (params or {}).get("page")
        event = events_fixture[page - 1]
        return _mock_response(
            {
                "events": [{"event": event}],
                "page": {"current": page, "size": 1, "total": 2},
            }
        )

    mock_client = AsyncMock()
    mock_client.get = fake_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("gaucho_agent.clients.ucsb_api.httpx.AsyncClient", return_value=mock_client):
        result = await client.get_events()

    assert captured_params == [{"page": 1}, {"page": 2}]
    assert [event["id"] for event in result] == ["evt-001", "evt-002"]
