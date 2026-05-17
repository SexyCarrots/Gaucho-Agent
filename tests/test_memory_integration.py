"""Day-5: MemoryBackend interface conformance across implementations."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from gaucho_agent.models.llm_cache import LLMCache  # noqa: F401  registers table
from gaucho_agent.models.memory import MemoryItem  # noqa: F401  registers table
from gaucho_agent.services.memory_backend import (
    Mem0Backend,
    NaiveRAGBackend,
    OursBackend,
    RecentWindowBackend,
    get_backend,
)


@pytest.fixture()
def session():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(e)
    with Session(e) as s:
        yield s


# --- factory ----------------------------------------------------------------

def test_factory_returns_expected_types(session):
    assert isinstance(get_backend("ours", session=session), OursBackend)
    assert isinstance(get_backend("naive_rag"), NaiveRAGBackend)
    assert isinstance(get_backend("recent_window"), RecentWindowBackend)


def test_factory_rejects_unknown():
    with pytest.raises(ValueError):
        get_backend("nope")


# --- contract conformance ---------------------------------------------------

@pytest.mark.parametrize("name", ["ours", "naive_rag", "recent_window"])
def test_retrieve_always_returns_list(session, name):
    b = get_backend(name, session=session)
    b.store(session, "I'm vegetarian", user_id="u")
    out = b.retrieve(session, "what do I eat?", user_id="u", k=5)
    assert isinstance(out, list)
    for m in out:
        assert hasattr(m, "content")


# --- behavioural differences ------------------------------------------------

def test_ours_filters_but_naive_stores_everything(session):
    ours = get_backend("ours", session=session)  # judge offline -> heuristic
    naive = get_backend("naive_rag")

    # A question is not a durable fact.
    assert ours.store(session, "what's for lunch?", user_id="a") is None
    assert naive.store(session, "what's for lunch?", user_id="b") is not None


def test_recent_window_has_no_long_term_memory(session):
    rw = get_backend("recent_window")
    assert rw.store(session, "I'm vegetarian", user_id="u") is None
    assert rw.retrieve(session, "what do I eat?", user_id="u") == []


def test_ours_overrides_but_naive_keeps_both(session):
    ours = get_backend("ours", session=session)
    ours.store(session, "I'm vegetarian", user_id="o", session_id="s1")
    ours.store(session, "I eat chicken now", user_id="o", session_id="s2")
    o_live = ours.retrieve(session, "what do I eat?", user_id="o", k=10)
    assert not any("vegetarian" in m.content for m in o_live)

    naive = get_backend("naive_rag")
    naive.store(session, "I'm vegetarian", user_id="n", session_id="s1")
    naive.store(session, "I eat chicken now", user_id="n", session_id="s2")
    n_live = naive.retrieve(session, "what do I eat?", user_id="n", k=10)
    assert len(n_live) == 2  # naive never supersedes


# --- mem0 graceful degradation ----------------------------------------------

def test_mem0_backend_errors_clearly_when_dep_missing():
    pytest.importorskip  # noqa: B018  (keep import-light)
    try:
        import mem0  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="pip install"):
            Mem0Backend()
    else:  # pragma: no cover - only when extra installed
        assert get_backend("mem0") is not None
