"""TypedDict / Pydantic schemas for tool inputs and outputs."""

from __future__ import annotations

from typing import Any, Optional, TypedDict


class AssignmentItem(TypedDict):
    id: int
    title: str
    course_code: Optional[str]
    course_name: Optional[str]
    due_at: Optional[str]
    url: Optional[str]
    description: Optional[str]


class AssignmentsOutput(TypedDict):
    query_window: dict[str, str]
    assignments: list[AssignmentItem]
    count: int


class ScheduleItem(TypedDict):
    id: int
    title: str
    course_code: Optional[str]
    start_at: Optional[str]
    end_at: Optional[str]
    location: Optional[str]
    all_day: bool


class TodayScheduleOutput(TypedDict):
    date: str
    events: list[ScheduleItem]
    count: int


class WorkloadOutput(TypedDict):
    query_window: dict[str, str]
    total_events: int
    by_day: dict[str, list[ScheduleItem]]


class DiningStatusItem(TypedDict):
    commons_code: str
    commons_name: str
    has_sack_meal: bool
    has_take_out_meal: bool
    has_dining_cam: bool


class DiningStatusOutput(TypedDict):
    commons: list[DiningStatusItem]
    count: int


class MenuItemOut(TypedDict):
    commons_name: str
    meal_code: str
    station_name: Optional[str]
    name: str
    dietary_info: Optional[str]


class DiningMenuOutput(TypedDict):
    date: str
    location_filter: Optional[str]
    items: list[MenuItemOut]
    count: int


class AcademicDateItem(TypedDict):
    id: int
    title: str
    category: Optional[str]
    start_at: Optional[str]
    end_at: Optional[str]
    all_day: bool


class AcademicDatesOutput(TypedDict):
    query_window: dict[str, str]
    dates: list[AcademicDateItem]
    count: int


class PlanBlock(TypedDict):
    time_range: str
    tasks: list[str]


class DailyPlanOutput(TypedDict):
    date: str
    available_hours: int
    morning: list[str]
    afternoon: list[str]
    evening: list[str]
    urgent: list[str]
    notes: list[str]


ToolResult = dict[str, Any]
