"""Day-7: generate synthetic Gaucho memory probes with gold annotations.

Each probe is a multi-session conversation that plants one durable fact
(the "needle"), buries it among distractor turns, and ends with a
memory-dependent question. Gold fields support EXP-4 (store/retrieve F1)
and EXP-5 (provenance).

Default mode is fully deterministic and offline so the file can be built
with no API key. With `--use-llm` and an OpenAI key, gpt-4o-mini
paraphrases turns for surface variety (cached via the llm_cache table).

    python scripts/build_synthetic_probes.py --n 50 --out data/synthetic_probes.json

Probe schema (per item):
    id, category, user_id, sessions[{session_id, turns[]}],
    question, gold_answer, gold_memory, gold_subject_key,
    needle_session, needle_turn_idx
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

# (subject_key, mem_type, fact_template, question, gold_answer)
_FACTS = [
    ("diet", "preference", "I'm vegetarian and don't eat any meat",
     "Can you suggest what I should get for dinner at the dining commons?",
     "vegetarian"),
    ("allergy", "profile", "I have a severe peanut allergy",
     "Is the pad thai at the dining commons safe for me?",
     "peanut allergy"),
    ("major", "profile", "My major is computer science",
     "Which department's advising should I contact about my courses?",
     "computer science"),
    ("advisor", "profile", "My advisor is Professor Singh",
     "Who should I email about my thesis committee?",
     "Professor Singh"),
    ("schedule", "schedule", "I have lab every Tuesday and Thursday at 2pm",
     "Am I free to meet a study group Tuesday at 2pm?",
     "no"),
    ("location", "profile", "I live in the San Nicolas residence hall",
     "Which dining commons is closest to where I live?",
     "San Nicolas"),
    ("plan", "plan", "I'm planning to take CS291A next quarter",
     "Remind me which class I said I'd enroll in next quarter?",
     "CS291A"),
    ("caffeine", "preference", "I don't drink coffee or any caffeine",
     "What should I grab to stay alert during late study sessions?",
     "no caffeine"),
]

_UPDATES = {
    "diet": ("Actually I started eating chicken again, I'm not vegetarian anymore",
             "Can you suggest what I should get for dinner?", "chicken"),
    "plan": ("I changed my mind, I'll take CS263 next quarter instead of CS291A",
             "Which class did I say I'd take next quarter?", "CS263"),
    "advisor": ("My advisor changed to Professor Lopez this term",
                "Who is my advisor now?", "Professor Lopez"),
}

_DISTRACTORS = [
    "I really like the color teal.",
    "The weather has been nice this week.",
    "My dorm room faces the east side.",
    "I watched a good movie last night.",
    "I think the bookstore is overpriced.",
    "I usually wake up around 8am.",
    "My favorite study spot has good lighting.",
    "I bought a new backpack recently.",
    "The bus was late again today.",
    "I prefer window seats in lecture halls.",
]

_QUESTION_TYPES = ["single_session", "multi_session", "knowledge_update",
                   "distractor", "profile"]


def _maybe_paraphrase(text: str, session, model: str) -> str:
    """Optional gpt-4o-mini paraphrase (cached). Falls back to identity."""
    from gaucho_agent.services import llm_cache

    key = llm_cache.make_key(model, "paraphrase:" + text, "probe-v1")
    cached = llm_cache.get_cached(session, key)
    if cached:
        return cached
    try:
        from gaucho_agent.services.memory_judge import _openai_complete

        out = _openai_complete(
            [{"role": "user",
              "content": f"Paraphrase, keep all facts, one sentence:\n{text}"}],
            model,
        ).strip()
    except Exception:
        out = text
    llm_cache.put_cache(session, key, model, out)
    return out


def build_probes(n: int, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    probes: list[dict] = []
    for i in range(n):
        subj, mem_type, fact, question, gold = _FACTS[i % len(_FACTS)]
        category = _QUESTION_TYPES[i % len(_QUESTION_TYPES)]
        uid = f"u{i:04d}"

        # Session 0: distractors + the needle fact.
        d = rng.sample(_DISTRACTORS, k=4)
        needle_turn_idx = rng.randint(1, 3)
        s0 = list(d)
        s0.insert(needle_turn_idx, fact)
        sessions = [{"session_id": f"{uid}-s0", "turns": s0}]

        # Extra noise session for multi/profile/distractor categories.
        if category in ("multi_session", "distractor", "profile"):
            sessions.append({
                "session_id": f"{uid}-s1",
                "turns": rng.sample(_DISTRACTORS, k=5),
            })

        q, ga, gmem, gsub = question, gold, fact, subj

        # knowledge_update: plant a contradicting fact in a later session.
        if category == "knowledge_update" and subj in _UPDATES:
            upd_fact, upd_q, upd_gold = _UPDATES[subj]
            sessions.append({
                "session_id": f"{uid}-s1",
                "turns": rng.sample(_DISTRACTORS, k=3) + [upd_fact],
            })
            q, ga, gmem = upd_q, upd_gold, upd_fact

        probes.append({
            "id": f"probe_{i:04d}",
            "category": category,
            "user_id": uid,
            "sessions": sessions,
            "question": q,
            "gold_answer": ga,
            "gold_memory": gmem,
            "gold_subject_key": gsub,
            "needle_session": 0,
            "needle_turn_idx": needle_turn_idx,
        })
    return probes


def main() -> int:
    ap = argparse.ArgumentParser(description="Build synthetic memory probes")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--out", default="data/synthetic_probes.json")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--use-llm", action="store_true",
                    help="paraphrase turns via gpt-4o-mini (needs OpenAI key)")
    ap.add_argument("--model", default="gpt-4o-mini")
    args = ap.parse_args()

    probes = build_probes(args.n, args.seed)

    if args.use_llm:
        from gaucho_agent.db import get_session, init_db

        init_db()
        with get_session() as s:
            for p in probes:
                for sess in p["sessions"]:
                    sess["turns"] = [
                        _maybe_paraphrase(t, s, args.model)
                        for t in sess["turns"]
                    ]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(probes, indent=2))
    cats = {}
    for p in probes:
        cats[p["category"]] = cats.get(p["category"], 0) + 1
    print(f"wrote {len(probes)} probes -> {out}")
    print("by category:", dict(sorted(cats.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
