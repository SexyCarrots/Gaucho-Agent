"""Lightweight Pydantic models for UCSB API responses."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class DiningCommonsResponse(BaseModel):
    name: str = ""
    code: str = ""
    has_sack_meal: bool = Field(default=False, alias="hasSackMeal")
    has_take_out_meal: bool = Field(default=False, alias="hasTakeOutMeal")
    has_dining_cam: bool = Field(default=False, alias="hasDiningCam")
    location: Optional[dict[str, Any]] = None

    model_config = {"populate_by_name": True}


class DiningMenuItemResponse(BaseModel):
    pass_id: str = Field(default="", alias="id")
    name: str = ""
    description: Optional[str] = None
    station: str = Field(default="", alias="stationName")
    meal_code: str = Field(default="", alias="mealCode")
    dietary_options: Optional[list[str]] = Field(default=None, alias="dietaryOptions")

    model_config = {"populate_by_name": True}


class QuarterCalendarEntry(BaseModel):
    quarter: str = ""
    quarter_year: Optional[str] = Field(default=None, alias="quarterYear")
    first_day_of_quarter: Optional[str] = Field(default=None, alias="firstDayOfClasses")
    last_day_of_classes: Optional[str] = Field(default=None, alias="lastDayOfClasses")
    first_day_of_finals: Optional[str] = Field(default=None, alias="firstDayOfFinals")
    last_day_of_finals: Optional[str] = Field(default=None, alias="lastDayOfFinals")

    model_config = {"populate_by_name": True}


class CampusEventResponse(BaseModel):
    id: Optional[str] = None
    title: str = ""
    description: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = Field(default=None, alias="startDate")
    end_date: Optional[str] = Field(default=None, alias="endDate")
    url: Optional[str] = None

    model_config = {"populate_by_name": True}
