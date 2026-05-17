"""LLMCache – persistent hash(prompt) -> response cache.

Keeps every gpt-4o-mini judge/eval call replayable for free, so re-runs
during Week 2 don't burn the token budget (EXPERIMENT_PLAN.md §9).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class LLMCache(SQLModel, table=True):
    __tablename__ = "llm_cache"

    cache_key: str = Field(primary_key=True)  # sha256 of (model, prompt, version)
    model: str = Field(index=True)
    response: str                              # raw model text (usually JSON)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    hit_count: int = 0
    id: Optional[int] = None  # unused; SQLModel friendliness
