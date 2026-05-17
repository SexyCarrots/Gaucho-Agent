"""Tests for the Week-2 shared eval harness (offline-forced)."""

from __future__ import annotations

from pathlib import Path

import pytest

from gaucho_agent.services import eval_runner as er
from gaucho_agent.services.memory_backend import get_backend


@pytest.fixture(autouse=True)
def _offline():
    er.set_offline(True)
    yield
    er.set_offline(False)


PROBE = {
    "id": "t1", "category": "single_session", "user_id": "tu",
    "sessions": [{"session_id": "tu-s0", "turns": [
        "I like the color blue.",
        "I'm vegetarian and don't eat any meat",
        "My dorm faces east.",
    ]}],
    "question": "what should I get for dinner?",
    "gold_answer": "vegetarian",
    "gold_memory": "I'm vegetarian and don't eat any meat",
    "gold_subject_key": "diet",
    "needle_session": 0, "needle_turn_idx": 1,
}


def test_est_tokens_monotonic():
    assert er.est_tokens("") == 0
    assert er.est_tokens("a" * 40) == 10


def test_gold_match_and_gold_in():
    assert er.gold_match(PROBE, "user is vegetarian and does not eat any meat")
    assert not er.gold_match(PROBE, "user's dorm faces east")
    assert er.gold_in(PROBE, ["noise", "user is vegetarian now"])


def test_fresh_session_isolated():
    with er.fresh_session() as s1:
        get_backend("ours", session=s1).store(s1, "I'm vegetarian", user_id="x")
    with er.fresh_session() as s2:
        out = get_backend("ours", session=s2).retrieve(
            s2, "food?", user_id="x")
    assert out == []  # separate in-memory DB -> nothing leaks


def test_ingest_answer_score_offline_ours():
    with er.fresh_session() as s:
        b = get_backend("ours", session=s)
        n = er.ingest_probe(b, PROBE, s)
        assert n >= 1
        r = er.answer_probe(b, PROBE, s, mode="with_memory")
        assert r.n_mem >= 1
        assert er.score_answer(s, PROBE, r) is True


def test_no_memory_mode_retrieves_nothing():
    with er.fresh_session() as s:
        b = get_backend("ours", session=s)
        er.ingest_probe(b, PROBE, s)
        r = er.answer_probe(b, PROBE, s, mode="no_memory")
        assert r.n_mem == 0
        assert r.mem_tokens == 0


def test_write_csv_roundtrip(tmp_path: Path):
    p = tmp_path / "r.csv"
    er.write_csv(str(p), [{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    lines = p.read_text().strip().splitlines()
    assert lines[0] == "a,b"
    assert lines[1] == "1,2"


def test_load_probes_reads_synthetic_file():
    path = "data/synthetic_probes.json"
    if not Path(path).exists():
        pytest.skip("synthetic probes not generated")
    probes = er.load_probes(path, n=5)
    assert len(probes) == 5
    assert {"id", "question", "gold_memory"} <= set(probes[0])
