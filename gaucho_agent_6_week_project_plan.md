# Gaucho-Agent: 6-Week Project Plan

## Project Summary
Build a distributable, local-first academic assistant for UCSB students that combines:
- Canvas **ICS calendar feed** ingestion
- UCSB APIs already approved for the app
- user-provided LLM API keys
- a small command/tool layer for planning and question answering

The baseline intentionally avoids protected student-record APIs and full Canvas OAuth. It uses what is already feasible now:
- Canvas private calendar feed URL (`.ics`)
- UCSB approved APIs:
  - Dining - Dining Commons
  - Dining - Dining Menu
  - Dining - Meal Plan Rates
  - Academics - Curriculums
  - Academics - Department Chairs
  - Academics - Events
  - Academics - CLAS Schedules
  - Academics - Academic Quarter Calendar
  - Students - Student Record Code Lookups

## Product Goal
A GitHub repo that any student can run locally by adding:
- their own Canvas ICS feed URL
- their own LLM API key
- optionally their UCSB API key if needed for public/approved UCSB endpoints

## Core User Stories
1. “What’s due today / this week?”
2. “Make me a plan for today around my deadlines.”
3. “What dining commons are open and what’s on the menu?”
4. “What campus events or academic dates matter this week?”
5. “Summarize my upcoming workload by course.”
6. “Given my calendar, when should I work on Project X?”

## Scope Boundaries
### In scope
- Canvas calendar feed parsing
- UCSB approved public-ish APIs
- LLM tool-calling / structured command execution
- local deployment for individual users
- simple CLI and/or local web app

### Out of scope for MVP
- protected UCSB student APIs still pending approval
- full Canvas login / OAuth integration
- grades, submissions, lecture file download, announcements
- production hosting / multi-tenant auth

## Architecture Choice
Local-first app:
- frontend: simple CLI first, optional lightweight web UI
- backend: Python service
- storage: SQLite
- ingestion jobs:
  - Canvas ICS fetch + parse
  - UCSB API fetchers
- agent layer:
  - prompts + tools + planner
- config:
  - `.env` for credentials
  - per-user local config file

---

## Week 1 — Finalize scope and bootstrap repo
### Goals
- Freeze MVP scope
- Create repo skeleton
- Set up config and secrets handling
- Prove Canvas ICS ingestion works end-to-end

### Deliverables
- GitHub repo initialized
- README with setup instructions
- `.env.example`
- module for fetching and parsing Canvas ICS feed
- normalized event schema in SQLite

### Tasks
- choose stack: Python + FastAPI + SQLite + Typer CLI
- define data model:
  - `events`
  - `assignments`
  - `sources`
  - `refresh_runs`
- implement:
  - fetch ICS from private URL
  - parse VEVENTs
  - normalize title, course, due time, description, URL
- add command:
  - `gaucho sync canvas`

### Success criteria
- user can paste Canvas feed URL and import all calendar events
- app can print upcoming assignments for next 7 days

---

## Week 2 — UCSB API integration baseline
### Goals
- Integrate all already approved APIs that are relevant to daily academic life
- Create stable wrappers and local caching

### Deliverables
- UCSB API client module
- cached sync jobs for:
  - dining commons
  - dining menu
  - meal plan rates
  - quarter calendar
  - events
  - CLAS schedules
- normalized local tables

### Tasks
- define generic UCSB client with API key header support
- implement endpoint wrappers
- normalize each source into internal schema
- add commands:
  - `gaucho sync dining`
  - `gaucho sync academics`
  - `gaucho sync all`

### Success criteria
- app can answer:
  - what dining commons are open?
  - what’s on the menu today?
  - what academic deadlines or dates are coming up?
  - what CLAS sessions are listed?

---

## Week 3 — Agent tools and baseline planner
### Goals
- Build first usable agent
- Convert raw data into tools the LLM can call

### Deliverables
- tool layer for querying local DB
- prompt templates
- baseline planner
- CLI chat loop

### Tools to implement
- `get_upcoming_assignments(days, course=None)`
- `get_today_schedule()`
- `get_upcoming_events(days)`
- `get_dining_commons_status()`
- `get_dining_menu(location, date)`
- `make_daily_plan(date, available_hours=None)`
- `summarize_workload(days)`

### Tasks
- define tool JSON schemas
- implement tool router
- create system prompt focused on UCSB student assistant behavior
- support OpenAI-compatible or Anthropic-compatible model adapters

### Success criteria
- user can ask natural language questions and get grounded answers from local data
- planner produces a reasonable day plan from deadlines + events

---

## Week 4 — Packaging, personalization, and robustness
### Goals
- Make the repo distributable to individual students
- Improve reliability and quality of answers

### Deliverables
- installer / setup script
- per-user config
- background refresh option
- better parsing / dedup / timezone handling
- docs for self-host/local run

### Tasks
- package as Python project
- add:
  - `gaucho init`
  - `gaucho doctor`
  - `gaucho config set`
- implement refresh scheduling:
  - manual
  - periodic local cron/task runner option
- add conflict handling:
  - duplicate Canvas events
  - all-day vs timed events
  - malformed descriptions
- refine course extraction from titles like `[CMPSC 291A S26]`

### Success criteria
- another student can clone repo, add credentials, and run it
- sync pipeline is stable across multiple refreshes

---

## Week 5 — Evaluation and demo scenarios
### Goals
- Turn the system into a class-project-quality evaluation
- Compare agent variants and gather evidence

### Evaluation plan
Compare:
1. no-agent templated query only
2. LLM without tools
3. LLM with tools on synced local data

Optional extra:
4. LLM with tools + daily planning heuristics

### Metrics
- task success on benchmark scenarios
- factual grounding / correctness
- latency
- user effort to configure
- qualitative usefulness

### Deliverables
- 15–25 scripted eval tasks
- result table
- screenshots / demo transcript
- error analysis

### Example eval tasks
- identify next 3 deadlines
- generate today’s work plan
- find dinner options after 6pm
- summarize weekly workload by course
- identify upcoming campus academic dates

### Success criteria
- tool-using agent clearly outperforms plain LLM on grounded campus tasks

---

## Week 6 — Polish, final report, and release candidate
### Goals
- Ship a clean demoable version
- Prepare course materials

### Deliverables
- release candidate repo
- final README
- architecture diagram
- demo script
- presentation slides
- report figures/tables

### Tasks
- improve prompts and fallback behavior
- finalize screenshots and walkthrough
- add sample config and mock dataset for demo without credentials
- write limitations section:
  - no protected student APIs
  - no full Canvas content
  - depends on ICS feed freshness
- record short demo

### Success criteria
- repo is runnable
- demo is smooth
- report has clear motivation, approach, evaluation, and limitations

---

## Risks and Mitigations
### Risk 1: ICS feed missing some useful course content
Mitigation:
- scope to calendar/deadline awareness only
- clearly state limitation

### Risk 2: UCSB endpoint quirks / rate limits
Mitigation:
- aggressive local caching
- sync once, query many times

### Risk 3: LLM hallucination
Mitigation:
- only answer from tool outputs
- include source snippets and timestamps in prompt context

### Risk 4: Time overrun
Mitigation:
- CLI first
- web UI optional
- no Canvas OAuth in MVP

---

## Final Demo Story
A UCSB student installs Gaucho-Agent locally, adds:
- Canvas ICS feed URL
- LLM API key
- UCSB API key

Then they can run:
- `gaucho chat`
- `gaucho sync all`

And ask:
- “What do I need to finish this week?”
- “Plan my day around my deadlines and dinner.”
- “What dining commons are open after my class?”
- “What campus dates should I care about this week?”
