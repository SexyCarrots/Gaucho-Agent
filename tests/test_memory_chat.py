"""Day-2 wiring: memory persists across independent sessions (no LLM)."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from gaucho_agent.models.memory import MemoryItem  # noqa: F401  registers table
from gaucho_agent.services.memory import MemoryService


def test_fact_recalled_in_separate_session(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'mem.db'}"

    eng1 = create_engine(url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng1)
    with Session(eng1) as s1:
        MemoryService().store(
            s1, "I'm vegetarian", user_id="p", session_id="a"
        )
    eng1.dispose()

    # Fresh engine + service = simulates a new `gaucho chat` process.
    eng2 = create_engine(url, connect_args={"check_same_thread": False})
    with Session(eng2) as s2:
        hits = MemoryService().retrieve(
            s2, "what can I eat for dinner?", user_id="p", k=5
        )
    eng2.dispose()

    assert any("vegetarian" in m.content for m in hits)


def test_chat_command_registered():
    """The chat command still imports/registers after memory wiring."""
    from gaucho_agent.cli.main import app

    names = {c.name or c.callback.__name__ for c in app.registered_commands}
    assert "chat" in names
