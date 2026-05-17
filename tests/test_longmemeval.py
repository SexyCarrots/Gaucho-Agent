"""Tests for the LongMemEval-S loader (uses a tiny inline fixture)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaucho_agent.services import longmemeval as lme

_FIX = [
    {
        "question_id": "q1",
        "question_type": "single-session-user",
        "question": "What did I study?",
        "answer": "Business Administration",
        "haystack_session_ids": ["q1-s0", "q1-s1"],
        "haystack_sessions": [
            [{"role": "user", "content": "Random small talk about a river puzzle."},
             {"role": "assistant", "content": "Here is an answer."}],
            [{"role": "user", "content": "I graduated in Business Administration.",
              "has_answer": True},
             {"role": "assistant", "content": "Great!"}],
        ],
    },
    {
        "question_id": "q2_abs",
        "question_type": "knowledge-update",
        "question": "Where do I work now?",
        "answer": "no information available",
        "haystack_session_ids": ["q2-s0"],
        "haystack_sessions": [
            [{"role": "user", "content": "The weather is nice."}],
        ],
    },
]


@pytest.fixture()
def lme_file(tmp_path: Path) -> str:
    p = tmp_path / "longmemeval_s.json"
    p.write_text(json.dumps(_FIX))
    return str(p)


def test_adapts_to_probe_schema(lme_file):
    probes = lme.load_longmemeval_s(lme_file)
    assert len(probes) == 2
    p = probes[0]
    assert {"id", "category", "user_id", "sessions", "question",
            "gold_answer", "gold_memory", "needle_session",
            "needle_turn_idx"} <= set(p)
    assert p["gold_answer"] == "Business Administration"
    # Only user turns are kept as memory candidates.
    all_turns = [t for s in p["sessions"] for t in s["turns"]]
    assert "I graduated in Business Administration." in all_turns
    assert "Here is an answer." not in all_turns


def test_evidence_turn_becomes_gold_memory_and_needle(lme_file):
    p = lme.load_longmemeval_s(lme_file)[0]
    assert "Business Administration" in p["gold_memory"]
    # needle is in the 2nd kept session, first user turn
    assert p["needle_session"] == 1
    assert p["needle_turn_idx"] == 0


def test_abstention_flag_detected(lme_file):
    p = lme.load_longmemeval_s(lme_file)[1]
    assert p["is_abstention"] is True


def test_stratified_subsample_balances_categories(lme_file):
    probes = lme.load_longmemeval_s(lme_file, n=2, stratified=True)
    cats = {p["category"] for p in probes}
    assert len(cats) == 2  # one of each, not two of the same


def test_is_available_false_for_missing(tmp_path):
    assert lme.is_available(str(tmp_path / "nope.json")) is False
