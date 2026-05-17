"""Day-4: judge-backed override + isolated type-aware scoring term."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from gaucho_agent.config import settings
from gaucho_agent.models.llm_cache import LLMCache  # noqa: F401  registers table
from gaucho_agent.models.memory import MemoryItem
from gaucho_agent.services import embeddings
from gaucho_agent.services.memory import MemoryService
from gaucho_agent.services.memory_judge import MemoryJudge, judge_decider


@pytest.fixture()
def session():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(e)
    with Session(e) as s:
        yield s


def test_judge_backed_contradiction_supersedes_old_fact(session):
    """'I'm vegetarian' then 'I eat chicken now' via judge -> only newer."""
    svc = MemoryService(
        decider=judge_decider(session, MemoryJudge(offline=True))
    )
    old = svc.store(session, "I'm vegetarian", user_id="u", session_id="s1")
    new = svc.store(session, "I eat chicken now", user_id="u", session_id="s2")

    session.refresh(old)
    assert old.superseded_by == new.id
    live = svc.retrieve(session, "what do I eat?", user_id="u", k=10)
    contents = [m.content for m in live]
    assert any("chicken" in c for c in contents)
    assert not any("vegetarian" in c for c in contents)


def test_type_match_term_breaks_ties(session):
    """Equal embeddings -> the type-matching memory wins by exactly β."""
    content = "Tuesday afternoon block"
    emb = embeddings.to_bytes(embeddings.embed(content))
    now = datetime.utcnow()
    sched = MemoryItem(
        user_id="u", session_id="s", content=content, raw_turn=content,
        mem_type="schedule", subject_key="schedule", created_at=now,
        embedding=emb,
    )
    pref = MemoryItem(
        user_id="u", session_id="s", content=content, raw_turn=content,
        mem_type="preference", subject_key="preference", created_at=now,
        embedding=emb,
    )
    session.add(sched)
    session.add(pref)
    session.commit()

    svc = MemoryService()
    scored = dict(
        (m.mem_type, sc)
        for m, sc in svc.retrieve_scored(
            session, "when is my lab on tuesday?", user_id="u", k=10
        )
    )
    # query infers type "schedule"; same embedding + same recency => the
    # only difference is β·I[type match].
    assert scored["schedule"] - scored["preference"] == pytest.approx(
        settings.mem_beta, abs=1e-5
    )


def test_chat_command_still_imports():
    from gaucho_agent.cli.main import app

    assert any(
        (c.name or c.callback.__name__) == "chat"
        for c in app.registered_commands
    )
