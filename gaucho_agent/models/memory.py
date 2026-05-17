"""MemoryItem – a single persisted fact in the selective-memory layer.

Schema mirrors EXPERIMENT_PLAN.md §4.1. The `embedding` column holds a
numpy float32 vector serialized with `.tobytes()`; use
`gaucho_agent.services.embeddings.from_bytes` to read it back.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

# preference  – likes/dislikes/diet ("user is vegetarian")
# profile     – stable identity facts ("user's major is CS", allergies)
# schedule    – recurring time commitments ("lab every Tue 2pm")
# plan        – intentions/one-off plans ("planning to take CS291A next quarter")
MEMORY_TYPES = ("preference", "profile", "schedule", "plan")


class MemoryItem(SQLModel, table=True):
    __tablename__ = "memory_item"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    session_id: str = Field(index=True)
    content: str                       # canonical fact ("user is vegetarian")
    raw_turn: str                      # original utterance (traceability)
    mem_type: str                      # one of MEMORY_TYPES
    subject_key: str = Field(index=True)  # override matching: "diet", "lab_schedule"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    embedding: bytes = b""             # numpy float32 as bytes
    superseded_by: Optional[int] = Field(default=None, index=True)
    # Provenance fields for EXP-5 / process forensics
    source_turn_idx: int = 0
    judge_confidence: float = 1.0      # 0..1 (1.0 for the Day-1 heuristic)
