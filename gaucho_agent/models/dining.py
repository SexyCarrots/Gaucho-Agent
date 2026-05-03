"""Dining models – commons status and menu items."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class DiningCommonsStatus(SQLModel, table=True):
    __tablename__ = "dining_commons_status"

    id: Optional[int] = Field(default=None, primary_key=True)
    commons_code: str = Field(unique=True, index=True)
    commons_name: str
    has_sack_meal: bool = False
    has_take_out_meal: bool = False
    has_dining_cam: bool = False
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    # open/closed status — populated by sync using /dining/menu/v1/{date}
    is_open_today: bool = Field(default=False)
    status_date: Optional[date] = Field(default=None)
    description: Optional[str] = None
    raw_json: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DiningMenuItem(SQLModel, table=True):
    __tablename__ = "dining_menu_item"

    id: Optional[int] = Field(default=None, primary_key=True)
    commons_code: str = Field(index=True)
    commons_name: str
    meal_code: str                        # breakfast | lunch | dinner | brunch
    name: str
    station_name: Optional[str] = None
    menu_date: date = Field(index=True)
    price: Optional[float] = None
    description: Optional[str] = None
    dietary_info: Optional[str] = None   # JSON array of tags
    raw_json: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
