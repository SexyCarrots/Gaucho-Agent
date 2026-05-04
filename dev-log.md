# Gaucho-Agent Dev Log

---

## 2026-05-04 — Dining fix, sync reduction, live campus tools

### Status
Four bugs fixed, two new tools added. All 41 tests passing.

### What changed

#### Dining open/closed fix
The previous sync used `/dining/commons/v1` (a static commons list) to determine open/closed status, so all four halls always appeared open regardless of the day. The UCSB Dining API uses a three-level path hierarchy:

- `/dining/menu/v1/{date}` — returns only commons codes that are **open** that day (absence = closed)
- `/dining/menu/v1/{date}/{commons_code}` — returns meal periods for that commons
- `/dining/menu/v1/{date}/{commons_code}/{meal_code}` — returns individual menu items

`services/sync_dining.py` was rewritten to probe the first level to establish open/closed status, then walk down the hierarchy to fetch today's menu. `DiningCommonsStatus` now stores `is_open_today` (bool) and `status_date` (date) so the tool can report staleness.

Result: Ortega correctly shows Closed on Saturday; Carrillo and De La Guerra show their actual per-day status.

#### Sync record count reduction (3,377 → 284)
Two separate issues caused the bloat:

1. **Quarter calendar**: `/academics/quartercalendar/v1/quarters` returns all 383 quarters from 1930 to 2034. With 13 milestones per quarter that was ~4,979 potential rows. Added `_quarter_year()` helper and filtered to `current_year+` only (≤ ~13 quarters, ≤ ~169 rows).

2. **Campus events**: The Localist API accepts `start_date`/`end_date` (not `start`/`end`). Wrong param names meant all pages were returned (~11 pages, ~hundreds of events). Fixed param names and added a 7-day window via `window_start`/`window_end`. Stale event rows are deleted before each sync.

Combined result: typical sync now upserts ~284 records instead of 3,377.

#### Live library and gym busyness tools
Two new tools added — both fetch live data at query time with no database involvement:

- **`get_library_busyness`** — calls `waitz.io/live/ucsb` (public, no auth). Returns open/closed sections with busyness 0–100 (percent of capacity). Data refreshes every ~3 minutes.
- **`get_gym_busyness`** — calls the GoBoard Azure API used by `recreation.ucsb.edu/facilities/livecount`. Returns occupancy grouped by facility area. The API's `PercetageCapacity` field is broken (always 0); actual percent is computed from `LastCount / TotalCapacity`.

New files: `gaucho_agent/clients/campus_live.py` (async fetch functions), `gaucho_agent/tools/campus.py` (sync wrappers using `asyncio.run()`).

The tool dispatcher in `services/tool_executor.py` now uses `inspect.signature(fn).parameters` to conditionally inject the DB `session` — live tools like these don't accept a session, so it's omitted automatically.

#### Retry fix (401 no longer retried)
`tenacity` retry decorator was using `retry_if_exception_type(httpx.HTTPStatusError)` which retried all HTTP errors including 401s. Changed to `retry_if_exception(_is_retryable)` where `_is_retryable` returns True only for 5xx status codes and network-level errors (timeouts, connect errors). Academic endpoints pending API approval now fail immediately instead of retrying 3×.

### Verification
- `gaucho sync dining` → Ortega marked closed on Saturday, Carrillo open with brunch/dinner menu
- `gaucho sync all` → 284 records upserted (down from 3,377)
- Chat: "is the library busy?" → returns per-section busyness from Waitz
- Chat: "how crowded is the gym?" → returns per-facility occupancy from GoBoard
- Full test suite: 41/41 passing

---

## 2026-05-02 — UCSB academic quarter calendar fixes

### Status
Academic quarter calendar sync fixed and verified against the live UCSB API. Full test suite now passes: 39/39.

### What changed
- `clients/ucsb_api.py` now calls the documented hierarchical quarter calendar endpoints:
  - `/academics/quartercalendar/v1/quarters`
  - `/academics/quartercalendar/v1/quarters/current`
- Removed the old incorrect root fetch behavior for quarter calendar data. The API does not accept a `quarter` query parameter on `/academics/quartercalendar/v1`; named quarter filtering is now done locally after fetching `/quarters`.
- `services/sync_academics.py` now parses UCSB quarter calendar timestamps correctly. The previous parser sliced by format-string length, which caused valid values like `2026-06-06T00:00:00` to become `None`.
- Quarter calendar sync now normalizes additional user-facing academic milestones into `Event` rows:
  - first day of quarter
  - first/last day of classes
  - first/last day of finals
  - finals week range
  - schedule end / quarter end
  - Pass 1, Pass 2, Pass 3 begin dates
  - fee deadline
  - add deadlines
  - last day of third week
- `utils/time.py` now uses `datetime.fromisoformat()` for safer ISO parsing.

### Verification
- Live `gaucho sync academics` reached `/academics/quartercalendar/v1/quarters` with `200 OK`.
- Resync stored real `start_at` values instead of `None`.
- `get_upcoming_academic_dates(days=60)` now returns relevant answers for chat, including:
  - `SPRING 2026 - Finals Week` from June 6-12, 2026
  - `FALL 2026 - Pass 1 Begins` on May 11, 2026 at 9:00 AM PDT
  - `SPRING 2026 - Schedule Ends (Quarter End)` on June 21, 2026
- Targeted UCSB tests pass: `tests/test_sync_academics.py` and `tests/test_ucsb_client.py`
- Full suite passes with the CLI Python environment: 39/39 tests.

### Notes
- The UCSB `/quartercalendar/v1/sessions` and `/quartercalendar/v1/sessions/current` endpoints currently return empty lists from the live API.
- The useful registration session fields are present on quarter objects from `/quartercalendar/v1/quarters`.
- Campus events were moved to the direct Localist-backed Campus Calendar API at `https://www.campuscalendar.ucsb.edu/api/2/events`. `clients/ucsb_api.py` now fetches that endpoint directly, paginates Localist responses, and `sync_academics.py` normalizes Localist `event_instances` into `Event` rows. The old `/academics/events/v1` 301 warning is resolved.
- The private tutoring schedules API is not integrated because it is not publicly accessible.

---

## 2026-05-02 — Full MVP implementation

### Status
Initial implementation complete. 57 files created, 35/35 tests passing.

### What was built

Starting from an empty repo (only markdown plan files), the full Gaucho-Agent stack was implemented across all layers.

#### Config and DB
- `gaucho_agent/config.py` — `pydantic-settings` `BaseSettings` singleton; loads from `.env`; no raw `os.environ` calls anywhere
- `gaucho_agent/db.py` — SQLModel engine with `init_db()` and `get_session()` context manager; database path comes from `GAUCHO_DB_PATH`

#### Data models (SQLite tables)
- `Event` — unified table for Canvas assignments and UCSB academic dates; deduped by `external_id` (= ICS UID or UCSB record ID)
- `Source` — tracks configured data sources with last sync metadata
- `DiningMenuItem` — per-item dining menu rows keyed by commons, station, meal, date
- `DiningCommonsStatus` — current open/closed status with hours
- `SyncRun` — audit log of every sync attempt with success flag, record count, and error text

#### Clients
- `clients/canvas_ics.py` — fetches ICS text, parses `VEVENT`s, normalizes all-day vs timed events, extracts course code from `[CMPSC 291A S26]` pattern via regex, strips HTML from descriptions
- `clients/ucsb_api.py` — `httpx.AsyncClient` with `ucsb-api-key` header, 30s timeout, tenacity retry (3 attempts, exponential backoff on 5xx/timeout); wrappers for all enabled endpoints
- `clients/llm_openai.py` — raw httpx to OpenAI chat completions API; handles `tool_calls` in response
- `clients/llm_anthropic.py` — Anthropic SDK; converts OpenAI-format tool schemas and messages to Anthropic format internally; normalizes response to same dict shape as the OpenAI client

#### UCSB API endpoints wired up
All APIs enabled in the Gaucho-Agent app as of this date:
- Dining - Dining Commons
- Dining - Dining Menu
- Dining - Meal Plan Rates
- Academics - Academic Quarter Calendar
- Academics - Events
- Academics - Curriculums
- Academics - Department Chairs
- Students - Student Record Code Lookups
- Academics - Grad Programs

#### Sync services
- `services/sync_canvas.py` — fetches Canvas ICS URL, upserts Events, records SyncRun
- `services/sync_dining.py` — fetches commons list/status and today + 2-day menu; upserts dining tables
- `services/sync_academics.py` — fetches quarter calendar and campus events; normalizes into Event table with `source_kind=ucsb_api`

#### Planner (deterministic, no LLM)
`services/planner.py` implements urgency scoring (0–100) based on:
- time until due (continuous decay)
- keyword elevation: `midterm`, `final`, `exam`, `project`, `proposal` raise score
- past events score 0

Plan output clusters tasks into morning (8–12), afternoon (12–17), evening (17–21) blocks and avoids time slots occupied by existing calendar events. Bug fixed during development: SQLite stores datetimes as naive UTC; planner was comparing naive event datetimes against timezone-aware `now` — resolved with a `_naive_utc()` normalizer.

#### Tool layer
7 tools exposed to the LLM, all returning serializable dicts:
- `get_upcoming_assignments(days, course)` — Canvas events within window, optionally filtered by course code
- `get_today_schedule()` — timed events + all-day deadlines for today
- `summarize_workload(days)` — grouped counts by course and day
- `get_dining_commons_status()` — current open/closed state for each commons
- `get_dining_menu(location, date)` — menu items, optionally filtered by commons and date
- `get_upcoming_academic_dates(days)` — quarter dates and campus events
- `make_daily_plan(date, available_hours)` — calls deterministic planner, returns agenda

Tool JSON schemas are in `services/tool_executor.py` in OpenAI function-calling format. The executor dispatches by name and injects the DB session.

#### CLI (`gaucho` entrypoint)
```
gaucho init              # create DB, verify config
gaucho doctor            # check env vars, DB, API reachability
gaucho sync canvas       # sync Canvas ICS feed
gaucho sync dining       # sync dining data
gaucho sync academics    # sync academic calendar and events
gaucho sync all          # run all three in sequence
gaucho upcoming [--days] # non-LLM assignment view
gaucho dining            # show dining status
gaucho plan today        # deterministic daily plan
gaucho chat              # interactive LLM chat loop with tool calling
```

Rich used throughout for formatted terminal output.

#### FastAPI server
`gaucho_agent/api/` — optional local API for future UI use:
- `POST /sync/{canvas,dining,academics}`
- `GET /status`
- `GET /events/upcoming?days=7`
- `GET /dining/status`
- `POST /chat` — body `{"message": str, "history": [...]}`

#### Tests (35/35 passing)
- `test_canvas_ics.py` — 10 tests: event count, UID extraction, all-day detection, course code parsing, HTML stripping, category assignment
- `test_planner.py` — 9 tests: urgency scoring for imminent/distant/past/keyword events, plan structure and capacity
- `test_tools.py` — 11 tests: tool outputs for assignments, schedule, dining, academics — run against in-memory SQLite seeded from fixtures
- `test_ucsb_client.py` — 5 tests: API key header, correct endpoint paths, query param forwarding, tenacity retry on 500

#### Demo / fixture data
- `tests/fixtures/sample.ics` — 5 realistic Canvas events (assignment due, timed lecture, all-day, with course codes)
- `tests/fixtures/ucsb/dining_commons.json` — sample commons list
- `tests/fixtures/ucsb/dining_menu.json` — sample menu items
- `tests/fixtures/ucsb/quarter_calendar.json` — sample quarter calendar
- `tests/fixtures/ucsb/events.json` — sample campus events
- `scripts/demo_seed.py` — seeds DB from fixtures and prints a summary; allows demo without live credentials

### Quick start
```bash
cp .env.example .env
# fill in UCSB_API_KEY, CANVAS_ICS_URL, and one LLM key
pip install -e .
gaucho init
gaucho sync all
gaucho chat
```

### Known limitations / out of scope for MVP
- No Canvas OAuth — uses private ICS feed URL only (no grades, submissions, announcements)
- No protected student APIs — Students - Courses, Schedules, Rosters, Photos, Student Academic Programs all pending/disabled
- No multi-user hosting — local SQLite only
- No web UI — CLI first; FastAPI server is a foundation for a future UI
- ICS feed freshness depends on Canvas export cadence

### Next steps
- Get remaining UCSB APIs approved (especially Students - Courses for richer schedule data)
- Add `gaucho config set` for per-user config without editing `.env` directly
- Add APScheduler background refresh option
- Build evaluation harness (Week 5 plan) with 15–25 scripted tasks
- Optional: minimal Streamlit or React frontend over the FastAPI server
