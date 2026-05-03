# Gaucho-Agent Implementation Plan for Coding Agent

## Objective
Build a local-first GitHub repo called `gaucho-agent` that individual UCSB students can run with:
- their own Canvas ICS feed URL
- their own LLM API key
- optionally their own UCSB API key

The system should ingest campus and course-calendar data, store it locally, expose structured tools, and support a CLI chat assistant for academic planning.

## Non-Goals
- Do not implement Canvas OAuth in MVP
- Do not implement protected UCSB student APIs
- Do not build production multi-user auth
- Do not depend on cloud databases
- Do not build mobile apps

---

## Tech Stack
### Required
- Python 3.11+
- FastAPI for local API server
- Typer for CLI
- SQLite for local storage
- SQLModel or SQLAlchemy
- `httpx` for HTTP
- `icalendar` for ICS parsing
- `pydantic` for schemas
- `python-dotenv` for config
- `rich` for terminal output

### Optional
- Streamlit or minimal React frontend later
- APScheduler for periodic refresh
- LiteLLM or thin provider abstraction for model backends

---

## Repo Structure
```text
gaucho-agent/
  README.md
  LICENSE
  .env.example
  pyproject.toml
  gaucho_agent/
    __init__.py
    config.py
    db.py
    models/
      event.py
      dining.py
      source.py
      sync_run.py
    schemas/
      canvas.py
      ucsb.py
      tool_io.py
    clients/
      canvas_ics.py
      ucsb_api.py
      llm_openai.py
      llm_anthropic.py
    services/
      sync_canvas.py
      sync_dining.py
      sync_academics.py
      planner.py
      retrieval.py
      tool_executor.py
    tools/
      assignments.py
      schedule.py
      dining.py
      academics.py
      planning.py
    prompts/
      system.txt
      planner.txt
    cli/
      main.py
    api/
      main.py
      routes_chat.py
      routes_sync.py
      routes_status.py
    utils/
      time.py
      parsing.py
      logging.py
  tests/
    test_canvas_ics.py
    test_ucsb_client.py
    test_planner.py
    test_tools.py
  scripts/
    bootstrap.sh
    demo_seed.py
```

---

## Configuration Model
Create `.env.example` with:
```env
GAUCHO_DB_PATH=./gaucho_agent.db
CANVAS_ICS_URL=
UCSB_API_BASE=https://api.ucsb.edu
UCSB_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
LOCAL_TIMEZONE=America/Los_Angeles
SYNC_USER_AGENT=gaucho-agent/0.1
```

Rules:
- Canvas ICS URL is optional but required for Canvas sync
- UCSB API key optional unless UCSB sync commands are used
- at least one LLM provider key required for chat/planning

---

## Data Model
Implement these SQLite tables.

### Source
Fields:
- id
- kind (`canvas_ics`, `ucsb_api`)
- name
- config_json
- last_success_at
- last_error
- created_at
- updated_at

### Event
Generic unified event table for assignments, campus dates, campus events, dining hours if useful.
Fields:
- id
- source_kind
- external_id
- title
- category
- course_code
- course_name
- start_at
- end_at
- all_day
- location
- description
- url
- raw_json
- created_at
- updated_at

### DiningMenuItem
Fields:
- id
- commons_name
- station_name
- item_name
- meal_name
- event_date
- dietary_tags_json
- raw_json

### DiningCommonsStatus
Fields:
- id
- commons_name
- open_status
- opens_at
- closes_at
- raw_json

### SyncRun
Fields:
- id
- source_kind
- started_at
- finished_at
- success
- records_upserted
- error_text

---

## Source Integrations

## 1. Canvas ICS Client
File: `clients/canvas_ics.py`

### Required behavior
- fetch ICS text from private feed URL
- parse `VEVENT`s
- normalize:
  - uid
  - summary
  - description
  - url
  - dtstart
  - dtend
  - all-day status
- extract course tag from summary if pattern like `[CMPSC 291A S26]`

### Functions
- `fetch_ics(url: str) -> str`
- `parse_ics(text: str) -> list[CanvasCalendarEvent]`
- `normalize_canvas_event(evt) -> EventUpsert`

### Edge cases
- all-day events with date-only values
- zero-duration due times
- duplicate UID refreshes
- missing description or URL

### Tests
- use provided sample ICS file fixture
- assert parsing of:
  - title
  - due date
  - course tag
  - Canvas URL

---

## 2. UCSB API Client
File: `clients/ucsb_api.py`

### Required behavior
- generic GET wrapper with `ucsb-api-key` header
- timeout + retry
- log response metadata
- return parsed JSON

### Functions
- `get(path: str, params: dict | None = None) -> dict | list`
- endpoint-specific wrappers:
  - `get_dining_commons()`
  - `get_dining_menu(date=None, commons=None)`
  - `get_meal_plan_rates()`
  - `get_academic_quarter_calendar()`
  - `get_events()`
  - `get_curriculums()`
  - `get_department_chairs()`
  - `get_student_record_code_lookups()`

### Implementation note
Keep wrappers thin. Normalize downstream in `services/`.

---

## Sync Services

## 1. Canvas Sync
File: `services/sync_canvas.py`

### Behavior
- load Canvas ICS URL from config
- fetch and parse feed
- upsert into `Event`
- store sync result in `SyncRun`

### Command
- `gaucho sync canvas`

## 2. Dining Sync
File: `services/sync_dining.py`

### Behavior
- fetch commons status
- fetch menu data for today
- optionally fetch next 2 days
- normalize into dining tables
- maybe also write commons opening hours into `Event`

### Command
- `gaucho sync dining`

## 3. Academics Sync
File: `services/sync_academics.py`

### Behavior
- fetch quarter calendar
- fetch campus events
- optionally fetch curriculums and department chairs
- normalize important dates/events into `Event`

### Command
- `gaucho sync academics`

## 4. Sync All
- `gaucho sync all`
- run canvas, dining, academics in sequence
- print success/failure summary

---

## Tool Layer
Implement tools as pure Python functions returning structured dictionaries.

## Tool 1: Upcoming assignments
File: `tools/assignments.py`
```python
def get_upcoming_assignments(days: int = 7, course: str | None = None) -> dict:
    ...
```
Returns:
- query window
- list of assignments/events from Canvas source
- due times
- URLs

## Tool 2: Today schedule
File: `tools/schedule.py`
```python
def get_today_schedule() -> dict:
    ...
```
Returns:
- today's timed events
- all-day deadlines
- campus dates

## Tool 3: Weekly workload
```python
def summarize_workload(days: int = 7) -> dict:
    ...
```
Returns grouped counts by course and urgency buckets.

## Tool 4: Dining status
File: `tools/dining.py`
```python
def get_dining_commons_status() -> dict:
    ...
```

## Tool 5: Dining menu
```python
def get_dining_menu(location: str | None = None, date: str | None = None) -> dict:
    ...
```

## Tool 6: Campus academic dates
File: `tools/academics.py`
```python
def get_upcoming_academic_dates(days: int = 14) -> dict:
    ...
```

## Tool 7: Make daily plan
File: `tools/planning.py`
```python
def make_daily_plan(date: str | None = None, available_hours: int | None = None) -> dict:
    ...
```
Implementation:
- compute urgency from due dates
- allocate work blocks
- include meal suggestions optionally

---

## Planner Heuristics
File: `services/planner.py`

Implement simple deterministic heuristic first:
- sort assignments by due time ascending
- raise priority if due within 48 hours
- raise priority if description/title contains keywords like `proposal`, `midterm`, `final`, `project`
- cluster into morning/afternoon/evening blocks
- optionally avoid known class/event times

Pseudo:
1. fetch today schedule
2. fetch next 7-day assignments
3. mark urgent tasks
4. place focused work blocks around fixed events
5. output a suggested agenda

Do not rely on LLM for scheduling math.

---

## LLM Integration
Implement thin provider abstraction.

### Interface
```python
class LLMClient(Protocol):
    def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict: ...
```

### Providers
- `clients/llm_openai.py`
- `clients/llm_anthropic.py`

### Required behavior
- take user prompt
- expose tools
- execute tool calls locally
- feed tool results back
- return final grounded answer

### System prompt requirements
Assistant should:
- act as UCSB-focused academic assistant
- never fabricate data not present in tool results
- cite source type in prose like:
  - “According to your Canvas calendar feed...”
  - “According to UCSB dining data...”
- prefer concise, actionable outputs

---

## CLI
File: `cli/main.py`

Commands:
```bash
gaucho init
gaucho doctor
gaucho sync canvas
gaucho sync dining
gaucho sync academics
gaucho sync all
gaucho chat
gaucho upcoming --days 7
gaucho dining
gaucho plan today
```

### Command behavior
- `init`: create config + DB
- `doctor`: verify env vars, DB, connectivity
- `chat`: interactive chat using tool-calling
- `upcoming`: plain non-LLM view
- `plan today`: deterministic plan, optional LLM narration

---

## Local API Server
File: `api/main.py`

Optional but useful for future UI.

Routes:
- `POST /sync/canvas`
- `POST /sync/dining`
- `POST /sync/academics`
- `GET /status`
- `POST /chat`
- `GET /events/upcoming`
- `GET /dining/status`

---

## Testing Requirements
### Unit tests
- ICS parsing
- UCSB client header injection
- DB upsert idempotence
- planner logic
- tool outputs

### Integration tests
- sync Canvas from fixture file
- sync mock UCSB endpoints from recorded JSON
- run one chat turn with mocked LLM tool call

### Fixtures
- provided Canvas ICS sample
- saved UCSB JSON examples once available

---

## Demo / Sample Data
Need a mock/demo mode so repo can run without private credentials.

Implement:
- `scripts/demo_seed.py`
- sample Canvas ICS file in `tests/fixtures/`
- mocked UCSB JSON payloads in `tests/fixtures/ucsb/`

README should explain:
- real mode
- demo mode

---

## README Requirements
README must include:
1. project description
2. supported data sources
3. limitations
4. install steps
5. setup `.env`
6. how to get Canvas ICS feed URL
7. how to get UCSB API key
8. how to choose LLM provider
9. CLI examples
10. security warnings

### Security section
- treat Canvas ICS URL as secret
- do not commit `.env`
- do not expose keys client-side
- use backend/server fetch for all secrets

---

## Milestone Breakdown for Coding Agent
### Milestone 1
Repo scaffold, config, DB, Canvas ICS parsing.

### Milestone 2
UCSB API wrappers and sync services.

### Milestone 3
Tool layer and deterministic planner.

### Milestone 4
LLM integration and CLI chat.

### Milestone 5
Packaging, docs, tests, demo mode.

---

## Acceptance Criteria
Project is complete when:
- a new user can clone the repo
- add Canvas ICS URL + LLM key
- optionally add UCSB API key
- run `gaucho sync all`
- ask “what’s due this week?” and get a grounded answer
- ask “plan my day” and get a usable response
- query dining status/menu successfully
- repo includes tests, docs, and demo mode

---

## Implementation Priority
Strict order:
1. Canvas ICS ingestion
2. local DB + sync commands
3. dining + academics UCSB APIs
4. deterministic planning
5. LLM tool-calling
6. packaging + docs
7. optional local web UI

Do not start with UI. Do not start with Canvas OAuth. Do not start with protected student APIs.
