"""Day-3 tests: LLM-as-judge contract, caching, parsing, offline fallback."""

from __future__ import annotations

import json

import pytest
from sqlmodel import Session, SQLModel, create_engine

from gaucho_agent.models.llm_cache import LLMCache  # noqa: F401  registers table
from gaucho_agent.models.memory import MEMORY_TYPES, MemoryItem  # noqa: F401
from gaucho_agent.services import llm_cache
from gaucho_agent.services.memory import MemoryService
from gaucho_agent.services.memory_judge import MemoryJudge, judge_decider

POSITIVES = [
    "I'm vegetarian",
    "I have a peanut allergy",
    "My name is Patrick",
    "My major is computer science",
    "I have lab every Tuesday at 2pm",
    "I'm planning to take CS291A next quarter",
    "I love spicy ramen",
    "I'm vegan",
    "My advisor is Dr. Smith",
    "I live in San Nicolas dorm",
]

NEGATIVES = [
    "What dining commons are open?",
    "When does the quarter end?",
    "Can you plan my day?",
    "thanks, that was helpful",
    "hello there",
    "how does this work",
    "show me my assignments",
    "tell me a joke",
    "ok",
    "is the library busy right now?",
]


@pytest.fixture()
def session():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(e)
    with Session(e) as s:
        yield s


# --- offline fallback: 10 positive / 10 negative -----------------------------

@pytest.mark.parametrize("turn", POSITIVES)
def test_offline_judge_stores_positives(turn):
    d = MemoryJudge(offline=True).judge(turn)
    assert d["store"] is True
    assert d["type"] in MEMORY_TYPES
    assert d["salient_fact"]


@pytest.mark.parametrize("turn", NEGATIVES)
def test_offline_judge_rejects_negatives(turn):
    d = MemoryJudge(offline=True).judge(turn)
    assert d["store"] is False


# --- parsing of model output -------------------------------------------------

def test_parses_clean_json_from_model():
    fake = lambda msgs: json.dumps({
        "store": True, "type": "preference",
        "salient_fact": "user is vegetarian", "subject_key": "diet",
        "confidence": 0.93, "supersedes": None,
    })
    d = MemoryJudge(complete_fn=fake).judge("I'm vegetarian")
    assert d["store"] and d["subject_key"] == "diet"
    assert d["confidence"] == pytest.approx(0.93)


def test_parses_json_wrapped_in_prose():
    fake = lambda msgs: (
        "Sure! Here is the judgement:\n```json\n"
        '{"store": true, "type": "profile", "salient_fact": "user has a '
        'peanut allergy", "subject_key": "allergy", "confidence": 0.99, '
        '"supersedes": null}\n```\nHope that helps.'
    )
    d = MemoryJudge(complete_fn=fake).judge("I have a peanut allergy")
    assert d["store"] and d["type"] == "profile"


def test_unparseable_output_falls_back_to_heuristic():
    d = MemoryJudge(complete_fn=lambda m: "totally not json").judge("I'm vegan")
    assert d["store"] is True  # heuristic still catches the diet fact


def test_invalid_type_is_coerced():
    fake = lambda m: json.dumps({
        "store": True, "type": "banana", "salient_fact": "user likes x",
        "subject_key": "preference", "confidence": 5,
    })
    d = MemoryJudge(complete_fn=fake).judge("I like x")
    assert d["type"] in MEMORY_TYPES
    assert 0.0 <= d["confidence"] <= 1.0


# --- caching by turn hash ----------------------------------------------------

def test_judge_caches_by_turn_hash(session):
    calls = {"n": 0}

    def counting(msgs):
        calls["n"] += 1
        return json.dumps({
            "store": True, "type": "preference",
            "salient_fact": "user is vegetarian", "subject_key": "diet",
            "confidence": 0.9, "supersedes": None,
        })

    j = MemoryJudge(complete_fn=counting)
    j.judge("I'm vegetarian", session=session)
    j.judge("I'm vegetarian", session=session)  # served from cache
    assert calls["n"] == 1
    assert llm_cache.cache_size(session) == 1

    j.judge("I have a peanut allergy", session=session)
    assert calls["n"] == 2
    assert llm_cache.cache_size(session) == 2


# --- integration with MemoryService -----------------------------------------

def test_judge_decider_plugs_into_memory_service(session):
    fake = lambda m: json.dumps({
        "store": True, "type": "preference",
        "salient_fact": "user is vegetarian", "subject_key": "diet",
        "confidence": 0.95, "supersedes": None,
    })
    svc = MemoryService(decider=judge_decider(session, MemoryJudge(complete_fn=fake)))
    item = svc.store(session, "I'm vegetarian", user_id="u1", session_id="s1")
    assert item is not None
    assert item.subject_key == "diet"
    assert item.judge_confidence == pytest.approx(0.95)
