"""Shared harness for the Week-2 experiment drivers.

Responsibilities
----------------
- `cached_complete` : one OpenAI call path, cached in `llm_cache` so
  re-runs are free (token-budget mitigation, §9).
- `ingest_probe`    : replay a probe's multi-session turns into a backend.
- `answer_probe`    : retrieve memories, build the prompt, produce an answer.
- `score_answer`    : LLM-as-judge correctness (§7 / LongMemEval protocol).

Offline behaviour: with no OpenAI key, `answer_probe` returns the retrieved
memories as the "answer" and `score_answer` checks whether the gold fact is
present in the retrieved set. This makes every driver runnable and
reproducible offline, where it measures *retrieval quality* — the
dominant factor the experiments compare — and upgrades transparently to
full generation+judge scoring when a key is configured.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from gaucho_agent.config import settings
from gaucho_agent.models.llm_cache import LLMCache  # noqa: F401  registers table
from gaucho_agent.models.memory import MemoryItem  # noqa: F401  registers table
from gaucho_agent.services import llm_cache

DEFAULT_PROBES = "data/synthetic_probes.json"


def load_probes(path: str = DEFAULT_PROBES, n: int | None = None) -> list[dict]:
    probes = json.loads(Path(path).read_text())
    return probes[:n] if n else probes


def _toks(s: str) -> set[str]:
    import re

    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def gold_match(probe: dict, text: str) -> bool:
    """True if `text` carries the probe's gold fact.

    Matches on the gold answer substring or strong token overlap with the
    gold memory (robust to the heuristic's 3rd-person normalization).
    """
    t = (text or "").lower()
    if str(probe["gold_answer"]).lower() in t:
        return True
    gm = _toks(probe["gold_memory"]) - {
        "i", "im", "i'm", "a", "an", "the", "and", "my", "is", "of", "to"
    }
    if not gm:
        return False
    overlap = len(gm & _toks(text)) / len(gm)
    return overlap >= 0.6


def gold_in(probe: dict, texts: list[str]) -> bool:
    return any(gold_match(probe, t) for t in texts)


def write_csv(path: str, rows: list[dict]) -> None:
    import csv

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text("")
        return
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


@contextmanager
def fresh_session():
    """Isolated in-memory DB so per-probe stores never leak across runs."""
    eng = create_engine("sqlite:///:memory:",
                         connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        yield s
    eng.dispose()


def set_offline(value: bool) -> None:
    """Force the offline proxy path everywhere (judge + harness).

    Routed through settings so lower-level components (MemoryJudge) honour
    it without importing this module.
    """
    settings.eval_offline = value


def _offline() -> bool:
    return settings.eval_offline or not settings.openai_api_key


def _has_key() -> bool:
    return not _offline()


def est_tokens(text: str) -> int:
    """Cheap ~4 chars/token estimate (good enough for ΔTokens / ROI)."""
    return max(len(text or "") // 4, 0)


def cached_complete(
    session: Session,
    messages: list[dict],
    model: str,
    *,
    version: str = "eval-v1",
    temperature: float = 0.0,
) -> str:
    """Cached OpenAI chat completion. Returns "" when offline."""
    if not _has_key():
        return ""
    prompt = "\x00".join(f'{m["role"]}:{m["content"]}' for m in messages)
    key = llm_cache.make_key(model, prompt, version)
    hit = llm_cache.get_cached(session, key)
    if hit is not None:
        return hit
    from gaucho_agent.services.memory_judge import _openai_complete

    try:
        out = _openai_complete(messages, model)
    except Exception:
        out = ""
    llm_cache.put_cache(session, key, model, out)
    return out


@dataclass
class ProbeResult:
    probe_id: str
    category: str
    correct: bool
    n_mem: int                       # memories injected
    mem_tokens: int                  # tokens added by the memory layer
    retrieved: list[str] = field(default_factory=list)
    retrieved_ids: list = field(default_factory=list)
    answer: str = ""


def ingest_probe(backend, probe: dict, session: Session) -> int:
    """Replay every session/turn of a probe into the backend's store."""
    stored = 0
    uid = probe["user_id"]
    for s in probe["sessions"]:
        for idx, turn in enumerate(s["turns"]):
            item = backend.store(
                session, turn, user_id=uid,
                session_id=s["session_id"], source_turn_idx=idx,
            )
            if item is not None:
                stored += 1
    return stored


def answer_probe(
    backend,
    probe: dict,
    session: Session,
    *,
    mode: str = "with_memory",
    model: str | None = None,
    k: int | None = None,
) -> ProbeResult:
    """Retrieve, build the prompt, and produce an answer for one probe."""
    model = model or settings.llm_model
    q = probe["question"]
    uid = probe["user_id"]

    retrieved, ids = [], []
    if mode == "with_memory":
        mems = backend.retrieve(session, q, user_id=uid, k=k)
        retrieved = [m.content for m in mems]
        ids = [getattr(m, "id", None) for m in mems]

    mem_block = "\n".join(f"- {c}" for c in retrieved)
    mem_tokens = est_tokens(mem_block)

    answer = ""
    if _has_key():
        # Prompt synced with gaucho_agent.cli.main chat() injection
        # (commit f301c27): recalled memories are HARD CONSTRAINTS, not
        # optional context. Otherwise the LLM retrieves the right fact
        # but ignores it, which biases EXP-1/3/ablations downward for
        # `ours` (the system whose advantage is delivering the right
        # fact to the prompt).
        sys = ("You are a UCSB academic assistant. Answer concisely.")
        if retrieved:
            user = (
                "PERSISTENT USER PROFILE — these facts about the user "
                "must be treated as HARD CONSTRAINTS on every "
                "recommendation in your answer, not as optional "
                f"context:\n{mem_block}\n\n"
                "Rules:\n"
                "1. Never recommend anything that contradicts a fact "
                "above (e.g. if the user is vegetarian, do not list "
                "meat, poultry, or fish).\n"
                "2. If the user's literal request conflicts with a "
                "fact, the fact wins; reframe the answer to satisfy "
                "the constraint.\n"
                "3. Briefly acknowledge the relevant fact you used.\n\n"
                f"Question: {q}"
            )
        else:
            user = f"Question: {q}"
        answer = cached_complete(
            session,
            [{"role": "system", "content": sys},
             {"role": "user", "content": user}],
            model,
            # Bump version so old cached responses (under the soft
            # "use if relevant" prompt) don't replay on this rerun.
            version="eval-v2-hardconstraints",
        )
    if not answer:
        # Offline proxy (no key, or call returned empty): the answer is
        # the recalled evidence itself, so scoring reduces to retrieval
        # quality — the dominant factor the experiments compare.
        answer = mem_block

    return ProbeResult(
        probe_id=probe["id"], category=probe["category"], correct=False,
        n_mem=len(retrieved), mem_tokens=mem_tokens,
        retrieved=retrieved, retrieved_ids=ids, answer=answer,
    )


def score_answer(
    session: Session,
    probe: dict,
    result: ProbeResult,
    *,
    judge_model: str = "gpt-4o",
) -> bool:
    """LLM-judge correctness with key; gold-in-evidence proxy offline."""
    gold = str(probe["gold_answer"]).lower()
    verdict = ""
    if _has_key():
        verdict = cached_complete(
            session,
            [{"role": "system",
              "content": "Reply with exactly 'yes' or 'no'."},
             {"role": "user",
              "content": (f"Question: {probe['question']}\n"
                          f"Reference answer: {probe['gold_answer']}\n"
                          f"Model answer: {result.answer}\n"
                          "Is the model answer correct?")}],
            judge_model,
            version="judge-v1",
        ).strip().lower()
    if verdict:
        result.correct = verdict.startswith("y")
    else:
        # Offline proxy: correct iff the gold fact is in the evidence.
        hay = (result.answer + " " + " ".join(result.retrieved)).lower()
        result.correct = gold in hay
    return result.correct
