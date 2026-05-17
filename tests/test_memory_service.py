"""Tests for the Day-1 selective-memory layer (heuristic policy)."""

from __future__ import annotations

import numpy as np
import pytest
from sqlmodel import Session, SQLModel, create_engine

from gaucho_agent.models.memory import MemoryItem  # noqa: F401  (registers table)
from gaucho_agent.services import embeddings
from gaucho_agent.services.memory import (
    MemoryService,
    heuristic_decider,
    infer_query_type,
)


@pytest.fixture()
def session():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(e)
    with Session(e) as s:
        yield s


# --- embeddings -------------------------------------------------------------

def test_embedding_is_deterministic_and_normalized():
    a = embeddings.embed("I am vegetarian")
    b = embeddings.embed("I am vegetarian")
    assert a.dtype == np.float32
    assert np.allclose(a, b)
    assert embeddings.cosine(a, a) == pytest.approx(1.0, abs=1e-5)


def test_embedding_roundtrip_bytes():
    v = embeddings.embed("peanut allergy")
    assert np.allclose(embeddings.from_bytes(embeddings.to_bytes(v)), v)


def test_related_text_more_similar_than_unrelated():
    q = embeddings.embed("what can I eat for dinner")
    diet = embeddings.embed("user is vegetarian and does not eat meat")
    far = embeddings.embed("user's lab is on Tuesday afternoon")
    assert embeddings.cosine(q, diet) > embeddings.cosine(q, far)


# --- heuristic store policy -------------------------------------------------

@pytest.mark.parametrize(
    "turn,subject,mem_type",
    [
        ("I'm vegetarian", "diet", "preference"),
        ("I have a peanut allergy", "allergy", "profile"),
        ("My name is Patrick", "name", "profile"),
        ("My major is computer science", "major", "profile"),
        ("I have lab every Tuesday at 2pm", "schedule", "schedule"),
        ("I'm planning to take CS291A next quarter", "plan", "plan"),
        ("I love spicy ramen", "preference", "preference"),
    ],
)
def test_heuristic_stores_personal_facts(turn, subject, mem_type):
    d = heuristic_decider(turn)
    assert d and d["store"]
    assert d["subject_key"] == subject
    assert d["type"] == mem_type


@pytest.mark.parametrize(
    "turn",
    [
        "What dining commons are open?",
        "When does the quarter end?",
        "Can you plan my day?",
        "hi",
    ],
)
def test_heuristic_skips_questions_and_noise(turn):
    assert heuristic_decider(turn) is None


def test_infer_query_type():
    assert infer_query_type("what should I eat tonight?") == "preference"
    assert infer_query_type("when is my lab?") == "schedule"
    assert infer_query_type("what's my major again?") == "profile"


# --- store / retrieve -------------------------------------------------------

def test_store_persists_with_cached_embedding(session):
    svc = MemoryService()
    item = svc.store(session, "I'm vegetarian", user_id="u1", session_id="s1")
    assert item is not None
    assert item.id is not None
    assert item.subject_key == "diet"
    assert len(item.embedding) > 0  # embedding cached in SQLite as bytes
    assert "vegetarian" in item.content


def test_store_skips_when_policy_declines(session):
    svc = MemoryService()
    assert svc.store(session, "what's for lunch?", user_id="u1") is None


def test_retrieve_ranks_relevant_memory_first(session):
    svc = MemoryService()
    svc.store(session, "I'm vegetarian", user_id="u1", session_id="s1")
    svc.store(session, "I have lab every Tuesday at 2pm", user_id="u1", session_id="s1")
    svc.store(session, "My major is computer science", user_id="u1", session_id="s1")

    top = svc.retrieve(session, "what can I eat for dinner?", user_id="u1", k=1)
    assert len(top) == 1
    assert "vegetarian" in top[0].content


def test_recency_override_returns_only_newer_fact(session):
    """'I'm vegetarian' then 'I eat chicken now' -> only the newer survives."""
    svc = MemoryService()
    old = svc.store(session, "I'm vegetarian", user_id="u1", session_id="s1")
    new = svc.store(session, "I eat chicken now", user_id="u1", session_id="s2")

    session.refresh(old)
    assert old.superseded_by == new.id

    live = svc.retrieve(session, "what do I eat?", user_id="u1", k=10)
    contents = [m.content for m in live]
    assert any("chicken" in c for c in contents)
    assert not any("vegetarian" in c for c in contents)


def test_users_are_isolated(session):
    svc = MemoryService()
    svc.store(session, "I'm vegetarian", user_id="alice", session_id="s1")
    svc.store(session, "I love steak", user_id="bob", session_id="s1")

    alice = svc.retrieve(session, "what do I eat?", user_id="alice", k=10)
    assert all(m.user_id == "alice" for m in alice)
    assert any("vegetarian" in m.content for m in alice)
