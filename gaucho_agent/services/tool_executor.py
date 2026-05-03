"""Tool executor – dispatches tool calls to the right function."""

from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session

from gaucho_agent.tools import assignments as t_assignments
from gaucho_agent.tools import schedule as t_schedule
from gaucho_agent.tools import dining as t_dining
from gaucho_agent.tools import academics as t_academics
from gaucho_agent.tools import planning as t_planning

# ---------------------------------------------------------------------------
# Tool JSON schemas (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_assignments",
            "description": "Get assignments and deadlines from Canvas calendar feed",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days ahead to look",
                        "default": 7,
                    },
                    "course": {
                        "type": "string",
                        "description": "Filter by course code (e.g. 'CMPSC 291A')",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_schedule",
            "description": "Get all scheduled events (classes, meetings) for today",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_workload",
            "description": "Summarize the number and distribution of events over the next N days",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look ahead",
                        "default": 7,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dining_commons_status",
            "description": (
                "Get whether each UCSB dining commons is open or closed today. "
                "is_open_today=true means open, false means closed, null means data not synced yet. "
                "Always call this first before answering any question about a dining hall being open."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dining_menu",
            "description": "Get dining menu items for a specific date and/or commons location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Commons name filter (e.g. 'Carrillo', 'De La Guerra')",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format; defaults to today",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_academic_dates",
            "description": "Get upcoming UCSB academic dates (quarter milestones, finals, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days ahead to look",
                        "default": 14,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_daily_plan",
            "description": "Generate a deterministic daily study/task plan",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format; defaults to today",
                    },
                    "available_hours": {
                        "type": "integer",
                        "description": "Total study hours available (default 8)",
                    },
                },
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "get_upcoming_assignments": t_assignments.get_upcoming_assignments,
    "get_today_schedule": t_schedule.get_today_schedule,
    "summarize_workload": t_schedule.summarize_workload,
    "get_dining_commons_status": t_dining.get_dining_commons_status,
    "get_dining_menu": t_dining.get_dining_menu,
    "get_upcoming_academic_dates": t_academics.get_upcoming_academic_dates,
    "make_daily_plan": t_planning.make_daily_plan,
}


def execute_tool(name: str, arguments: dict[str, Any], session: Session) -> dict[str, Any]:
    """Dispatch a tool call by name and return a serializable result dict."""
    fn = _DISPATCH.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}

    # Inject session into kwargs
    kwargs: dict[str, Any] = {**arguments, "session": session}
    try:
        result = fn(**kwargs)
    except TypeError as exc:
        # In case of signature mismatch – surface a useful error
        return {"error": str(exc)}

    if isinstance(result, dict):
        return result
    return {"result": result}
