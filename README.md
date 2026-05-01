# Gaucho-Agent

A local-first academic assistant for UCSB students that uses a private Canvas calendar feed, selected UCSB APIs, and an LLM to help with daily academic planning.

Gaucho-Agent is designed as a practical tool-using agent system rather than a generic chatbot. It syncs structured campus data into a local database, exposes a small set of tools, and uses an LLM to answer grounded questions like:

- What is due this week?
- Plan my day around my deadlines and dinner.
- What dining commons are open after class?
- What academic dates or CLAS sessions are coming up?

## Features

- Canvas calendar feed ingestion via private `.ics` URL
- UCSB API integration for approved endpoints
- Local SQLite storage
- CLI-first workflow
- Tool-using LLM assistant
- Local-first design so users can run it with their own credentials and API keys
- Demo-friendly architecture with clear sync and query commands

## Current Scope

This project currently focuses on:
- upcoming assignments and deadlines from Canvas calendar feed
- dining commons status and menus
- campus academic dates and events
- CLAS schedules
- simple daily planning and workload summarization

This project does **not** currently support:
- full Canvas content access
- grades or submissions
- protected UCSB student-record APIs
- GOLD integration
- multi-user cloud deployment

## Architecture Overview

Gaucho-Agent has four main layers:

1. **Ingestion**
   - fetches Canvas ICS feed
   - fetches UCSB API data

2. **Storage**
   - normalizes all synced data into a local SQLite database

3. **Tool Layer**
   - exposes structured functions such as:
     - `get_upcoming_assignments`
     - `get_today_schedule`
     - `get_dining_commons_status`
     - `get_dining_menu`
     - `get_upcoming_academic_dates`
     - `make_daily_plan`

4. **LLM Agent**
   - interprets user requests
   - calls tools
   - generates grounded responses based on tool outputs

## Repository Structure

```text
gaucho-agent/
  README.md
  .env.example
  pyproject.toml
  gaucho_agent/
    config.py
    db.py
    models/
    schemas/
    clients/
    services/
    tools/
    prompts/
    cli/
    api/
    utils/
  tests/
  scripts/
