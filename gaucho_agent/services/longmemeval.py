"""LongMemEval-S loader (EXPERIMENT_PLAN.md Day 6, §10).

LongMemEval-S (Wu et al., ICLR 2025; HF: ``xiaowu0162/longmemeval``)
ships one JSON list. Each record:

    {
      "question_id": "...",          # "_abs" suffix => abstention question
      "question_type": "single-session-user" | "multi-session" | ...,
      "question": "...",
      "answer": "...",
      "haystack_session_ids": [...],
      "haystack_sessions": [[{role, content, has_answer?}, ...], ...],
      "answer_session_ids": [...],
    }

We adapt it to the project's probe schema so the existing
``eval_runner``/backends work unchanged: user turns become memory-store
candidates, evidence turns (``has_answer``) become the gold memory.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_PATH = "data/longmemeval_s/longmemeval_s.json"
HF_REPO = "xiaowu0162/longmemeval"
HF_FILE = "longmemeval_s"


def is_available(path: str = DEFAULT_PATH) -> bool:
    return Path(path).exists()


def download(dest: str = DEFAULT_PATH) -> str:
    """Fetch longmemeval_s from HuggingFace into `dest`. Returns the path."""
    from huggingface_hub import hf_hub_download

    p = Path(dest)
    p.parent.mkdir(parents=True, exist_ok=True)
    cached = hf_hub_download(
        repo_id=HF_REPO, repo_type="dataset", filename=HF_FILE
    )
    data = Path(cached).read_bytes()
    # The HF file is extensionless JSON; normalize to our .json path.
    p.write_bytes(data)
    return str(p)


def _adapt(rec: dict, idx: int) -> dict:
    qid = rec.get("question_id") or f"lme_{idx:05d}"
    sessions_in = rec.get("haystack_sessions") or []
    sids = rec.get("haystack_session_ids") or [
        f"{qid}-s{i}" for i in range(len(sessions_in))
    ]

    sessions: list[dict] = []
    gold_turns: list[str] = []
    needle_session = 0
    needle_turn_idx = 0
    found_needle = False

    for si, sess in enumerate(sessions_in):
        turns: list[str] = []
        for turn in sess:
            if not isinstance(turn, dict):
                continue
            content = (turn.get("content") or "").strip()
            if not content:
                continue
            # Only user utterances carry personal facts to remember.
            if turn.get("role") == "user":
                if turn.get("has_answer") and not found_needle:
                    needle_session = len(sessions)
                    needle_turn_idx = len(turns)
                    found_needle = True
                if turn.get("has_answer"):
                    gold_turns.append(content)
                turns.append(content)
        if turns:
            sid = sids[si] if si < len(sids) else f"{qid}-s{si}"
            sessions.append({"session_id": str(sid), "turns": turns})

    answer = str(rec.get("answer", "")).strip()
    gold_mem = " ".join(gold_turns) if gold_turns else answer
    return {
        "id": str(qid),
        "category": str(rec.get("question_type") or "longmemeval"),
        "user_id": str(qid),
        "sessions": sessions,
        "question": str(rec.get("question", "")).strip(),
        "gold_answer": answer,
        "gold_memory": gold_mem,
        "gold_subject_key": "lme",
        "needle_session": needle_session,
        "needle_turn_idx": needle_turn_idx,
        "is_abstention": str(qid).endswith("_abs"),
    }


def load_longmemeval_s(
    path: str = DEFAULT_PATH,
    n: int | None = None,
    *,
    stratified: bool = True,
) -> list[dict]:
    """Load and adapt LongMemEval-S into probe dicts.

    `stratified` keeps the category mix when subsampling (the report's
    5-axis decomposition depends on balanced categories).
    """
    raw = json.loads(Path(path).read_text())
    probes = [_adapt(r, i) for i, r in enumerate(raw)]
    if n is None or n >= len(probes):
        return probes

    if not stratified:
        return probes[:n]

    by_cat: dict[str, list[dict]] = {}
    for p in probes:
        by_cat.setdefault(p["category"], []).append(p)
    cats = sorted(by_cat)
    out: list[dict] = []
    i = 0
    while len(out) < n:
        c = cats[i % len(cats)]
        if by_cat[c]:
            out.append(by_cat[c].pop(0))
        i += 1
        if i > len(probes) * 2:  # safety
            break
    return out[:n]
