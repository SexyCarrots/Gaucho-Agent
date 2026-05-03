# Gaucho-Agent

A local-first academic assistant for UCSB students. It syncs your Canvas calendar feed and UCSB campus data into a local database, then lets you ask natural-language questions through a CLI chat interface powered by an LLM of your choice.

```
$ gaucho chat
You: what's due this week?
Assistant: According to your Canvas calendar feed, you have 3 upcoming deadlines...

You: plan my day
Assistant: Here's a suggested plan for today based on your deadlines and dining hours...
```

## What it does

- Pulls your Canvas assignment deadlines from your private `.ics` feed URL
- Fetches live UCSB data: dining commons status, menus, academic quarter calendar, campus events
- Stores everything in a local SQLite database — no cloud, no accounts
- Exposes a set of tools the LLM calls to answer grounded questions (no hallucination from thin air)
- Works with OpenAI or Anthropic models using your own API key

## What it does not do

- No Canvas OAuth — only the private ICS feed (no grades, submissions, or announcements)
- No protected student APIs (schedules, rosters, photos) — those require institutional approval
- No GOLD integration
- No multi-user or cloud deployment

---

## Requirements

- Python 3.11+
- A UCSB Canvas account (for the ICS feed URL)
- An OpenAI or Anthropic API key
- Optionally a UCSB API key (for dining and academic data)

---

## Installation

```bash
git clone https://github.com/your-username/gaucho-agent.git
cd gaucho-agent
pip install -e .
```

---

## Setup

### 1. Copy the env file

```bash
cp .env.example .env
```

### 2. Get your Canvas ICS feed URL

1. Log in to [ucsb.instructure.com](https://ucsb.instructure.com)
2. Go to **Calendar** (left sidebar)
3. Click the **Calendar Feed** link at the bottom right
4. Copy the full URL — it looks like `https://ucsb.instructure.com/feeds/calendars/user_XXXX.ics`
5. Paste it into `.env` as `CANVAS_ICS_URL`

> **Keep this URL secret.** It gives read access to your full calendar without a password. Never commit it to git.

### 3. Get a UCSB API key

1. Go to [developer.ucsb.edu](https://developer.ucsb.edu)
2. Sign in with your UCSB NetID
3. Create an app and request access to the APIs you need (Dining, Academics)
4. Copy the Consumer Key and paste it into `.env` as `UCSB_API_KEY`

### 4. Add an LLM API key

For OpenAI:
```env
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
```

For Anthropic:
```env
ANTHROPIC_API_KEY=sk-ant-...
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5-20251001
```

### 5. Initialize

```bash
gaucho init
```

This creates the local database and checks your configuration.

---

## Usage

### Sync data

Pull fresh data from Canvas and UCSB:

```bash
gaucho sync all          # sync everything
gaucho sync canvas       # Canvas assignments only
gaucho sync dining       # dining status and menus
gaucho sync academics    # quarter calendar and events
```

Run this whenever you want fresh data. Canvas ICS feeds update periodically as instructors post assignments.

### Chat

Ask questions in natural language:

```bash
gaucho chat
```

Example questions:
- `what's due this week?`
- `plan my day`
- `what dining commons are open right now?`
- `what's on the menu at De La Guerra tonight?`
- `when does this quarter end?`
- `summarize my workload for the next 7 days`

Type `exit` or `quit` to leave the chat.

### Quick commands (no LLM)

```bash
gaucho upcoming              # show assignments for the next 7 days
gaucho upcoming --days 14    # extend the window
gaucho dining                # show which commons are open
gaucho plan today            # deterministic daily plan without LLM
```

### Health check

```bash
gaucho doctor
```

Checks that your env vars are set, the database exists, and the UCSB API is reachable.

---

## Demo mode (no credentials needed)

To try the project without real credentials, seed the database with fixture data:

```bash
python scripts/demo_seed.py
gaucho upcoming
gaucho dining
gaucho plan today
```

This loads sample Canvas events and UCSB data from `tests/fixtures/`.

---

## Configuration reference

All configuration lives in `.env`:

| Variable | Required | Description |
|---|---|---|
| `GAUCHO_DB_PATH` | No | Path to SQLite file (default: `./gaucho_agent.db`) |
| `CANVAS_ICS_URL` | For Canvas sync | Your private Canvas calendar feed URL |
| `UCSB_API_BASE` | No | UCSB API base URL (default: `https://api.ucsb.edu`) |
| `UCSB_API_KEY` | For UCSB sync | Your UCSB developer API key |
| `OPENAI_API_KEY` | One LLM key required | OpenAI API key |
| `ANTHROPIC_API_KEY` | One LLM key required | Anthropic API key |
| `LLM_PROVIDER` | No | `openai` or `anthropic` (default: `openai`) |
| `LLM_MODEL` | No | Model name (default: `gpt-4o-mini`) |
| `LOCAL_TIMEZONE` | No | Your timezone (default: `America/Los_Angeles`) |

---

## UCSB APIs used

The following UCSB API endpoints are integrated:

| API | Used for |
|---|---|
| Dining - Dining Commons | Commons list and open/closed status |
| Dining - Dining Menu | Daily menus by commons |
| Dining - Meal Plan Rates | Meal plan pricing |
| Academics - Academic Quarter Calendar | Quarter start/end dates, finals |
| Academics - Events | Campus events |
| Academics - Curriculums | Course curriculum data |
| Academics - Department Chairs | Department contact info |
| Students - Student Record Code Lookups | Academic code lookups |

---

## Project structure

```
gaucho_agent/
  config.py          # settings loaded from .env
  db.py              # SQLite engine and session
  models/            # SQLModel database tables
  schemas/           # Pydantic schemas for API responses
  clients/           # Canvas ICS, UCSB API, OpenAI, Anthropic
  services/          # sync jobs, planner, retrieval, tool executor
  tools/             # tool functions called by the LLM
  prompts/           # system and planner prompt templates
  cli/               # Typer CLI entrypoint
  api/               # FastAPI server (optional, for future UI)
  utils/             # time, parsing, logging helpers
tests/
  fixtures/          # sample ICS and UCSB JSON for testing/demo
scripts/
  demo_seed.py       # seed DB from fixtures without real credentials
```

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/
```

All 35 tests run against local fixtures — no credentials or network needed.

---

## Security notes

- Treat your Canvas ICS URL like a password — it grants read access to your full calendar
- Never commit `.env` to git (it is already in `.gitignore`)
- Your API keys never leave your machine; all requests are made locally
- The local SQLite database contains your personal calendar data — store it somewhere appropriate

---

## Limitations

- Canvas data is limited to what appears in the ICS feed (assignments, due dates, events). Grades, submission history, and announcements are not accessible without Canvas OAuth.
- UCSB APIs that are still pending approval (Courses, Schedules, Rosters, Student Records) are not integrated in this version.
- ICS feed freshness depends on how often Canvas exports updates — typically within a few minutes of instructor changes.
- The deterministic planner is heuristic-based; it does not know your actual work pace or preferences.
