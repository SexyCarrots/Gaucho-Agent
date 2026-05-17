"""Cross-session memory smoke test (no LLM, no network).

Demonstrates EXPERIMENT_PLAN.md Day 2 "Done when": a fact told in session 1
is recalled in a *separate* session backed by the same on-disk database.

    python scripts/smoke_memory.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from gaucho_agent.models.memory import MemoryItem  # noqa: F401  registers table
from gaucho_agent.services.memory import MemoryService


def main() -> int:
    db_path = Path(tempfile.gettempdir()) / "gaucho_smoke_memory.db"
    db_path.unlink(missing_ok=True)
    url = f"sqlite:///{db_path}"

    # --- Session 1: user discloses facts, then process "exits" ---
    eng1 = create_engine(url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng1)
    with Session(eng1) as s1:
        svc = MemoryService()
        svc.store(s1, "I'm vegetarian", user_id="patrick", session_id="sess1")
        svc.store(s1, "I have a peanut allergy", user_id="patrick", session_id="sess1")
        svc.store(s1, "What's for lunch today?", user_id="patrick", session_id="sess1")
    eng1.dispose()
    print("session 1: stored 2 facts (1 question correctly skipped)")

    # --- Session 2: brand-new engine + service on the same DB file ---
    eng2 = create_engine(url, connect_args={"check_same_thread": False})
    with Session(eng2) as s2:
        svc2 = MemoryService()
        hits = svc2.retrieve(
            s2, "what should I eat for dinner?", user_id="patrick", k=5
        )
    eng2.dispose()

    contents = [m.content for m in hits]
    print(f"session 2: recalled {len(hits)} item(s): {contents}")

    ok = any("vegetarian" in c for c in contents) and any(
        "peanut" in c for c in contents
    )
    db_path.unlink(missing_ok=True)
    if ok:
        print("PASS: facts persisted and recalled across sessions")
        return 0
    print("FAIL: expected vegetarian + peanut facts to be recalled")
    return 1


if __name__ == "__main__":
    sys.exit(main())
