"""Uniform memory backend interface: ours | naive_rag | recent_window | mem0.

All Week-2 experiment drivers and the chat loop talk to this interface so
swapping a system is a one-line change (EXPERIMENT_PLAN.md §4, §11).

Contract
--------
- ``store(session, turn, *, user_id, session_id, source_turn_idx)``
  -> a memory-like object (has ``.content``, ``.id``, ``.mem_type``) or
  ``None`` if the backend chose not to store this turn.
- ``retrieve(session, query, *, user_id, k)`` -> list of memory-like
  objects, best first.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session

from gaucho_agent.config import settings
from gaucho_agent.models.memory import MemoryItem
from gaucho_agent.services.memory import MemoryService, StoreDecision


@dataclass
class RecalledMemory:
    """Lightweight uniform view for non-SQLModel backends (mem0)."""

    content: str
    id: Optional[str | int] = None
    mem_type: str = "preference"


def _store_all_decider(turn: str) -> Optional[StoreDecision]:
    """Naive RAG: keep every non-empty turn verbatim, no curation."""
    t = (turn or "").strip()
    if not t:
        return None
    return {
        "store": True,
        "type": "preference",
        "salient_fact": t,
        "subject_key": f"raw:{uuid.uuid4().hex}",  # never supersedes
        "confidence": 1.0,
    }


class MemoryBackend(ABC):
    name: str = "base"

    @abstractmethod
    def store(self, session: Session, turn: str, *, user_id: str = "default",
              session_id: str = "default", source_turn_idx: int = 0): ...

    @abstractmethod
    def retrieve(self, session: Session, query: str, *,
                 user_id: str = "default", k: int | None = None) -> list: ...


class OursBackend(MemoryBackend):
    """Selective memory: judge store + type/recency retrieval + override."""

    name = "ours"

    def __init__(self, session: Session | None = None, judge=None,
                 use_judge: bool | None = None, **weights):
        decider = None
        if use_judge is None:
            use_judge = settings.memory_use_judge
        if use_judge:
            from gaucho_agent.services.memory_judge import (
                MemoryJudge,
                judge_decider,
            )

            decider = judge_decider(session, judge or MemoryJudge())
        self._svc = MemoryService(decider=decider, enable_override=True,
                                  **weights)

    def store(self, session, turn, *, user_id="default",
              session_id="default", source_turn_idx=0):
        return self._svc.store(session, turn, user_id=user_id,
                               session_id=session_id,
                               source_turn_idx=source_turn_idx)

    def retrieve(self, session, query, *, user_id="default", k=None):
        return self._svc.retrieve(session, query, user_id=user_id, k=k)


class NaiveRAGBackend(MemoryBackend):
    """Store every turn; retrieve by pure cosine (no type/recency/override)."""

    name = "naive_rag"

    def __init__(self, **_):
        self._svc = MemoryService(
            decider=_store_all_decider,
            alpha=1.0, beta=0.0, gamma=0.0, enable_override=False,
        )

    def store(self, session, turn, *, user_id="default",
              session_id="default", source_turn_idx=0):
        return self._svc.store(session, turn, user_id=user_id,
                               session_id=session_id,
                               source_turn_idx=source_turn_idx)

    def retrieve(self, session, query, *, user_id="default", k=None):
        return self._svc.retrieve(session, query, user_id=user_id, k=k)


class RecentWindowBackend(MemoryBackend):
    """No long-term memory. The model only ever sees the recent chat window.

    This is the counterfactual ``no_memory`` control in EXP-1: store is a
    no-op and retrieve is always empty.
    """

    name = "recent_window"

    def __init__(self, **_):
        pass

    def store(self, session, turn, *, user_id="default",
              session_id="default", source_turn_idx=0):
        return None

    def retrieve(self, session, query, *, user_id="default", k=None):
        return []


class Mem0Backend(MemoryBackend):
    """Baseline: the mem0 library (optional dep, pinned mem0ai==0.1.40)."""

    name = "mem0"

    def __init__(self, **_):
        try:
            from mem0 import Memory
        except ImportError as exc:  # pragma: no cover - exercised only w/o dep
            raise RuntimeError(
                "mem0 backend requires the optional dependency: "
                "pip install -e '.[memory]'"
            ) from exc
        self._mem = Memory()

    def store(self, session, turn, *, user_id="default",
              session_id="default", source_turn_idx=0):
        res = self._mem.add(turn, user_id=user_id)
        items = (res or {}).get("results") or []
        if not items:
            return None
        first = items[0]
        return RecalledMemory(content=first.get("memory", turn),
                              id=first.get("id"))

    def retrieve(self, session, query, *, user_id="default", k=None):
        k = k or settings.mem_top_k
        res = self._mem.search(query, user_id=user_id, limit=k)
        items = (res or {}).get("results") or []
        return [RecalledMemory(content=i.get("memory", ""), id=i.get("id"))
                for i in items]


_REGISTRY = {
    "ours": OursBackend,
    "naive_rag": NaiveRAGBackend,
    "recent_window": RecentWindowBackend,
    "mem0": Mem0Backend,
}


def get_backend(name: str, **kwargs) -> MemoryBackend:
    """Factory. `name` in {ours, naive_rag, recent_window, mem0}."""
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown memory backend: {name!r}. "
            f"Choose from {sorted(_REGISTRY)}."
        )
    return cls(**kwargs)
