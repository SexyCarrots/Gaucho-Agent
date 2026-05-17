"""EXP-3: turn clean probes into adversarial multi-session conversations.

Deterministic offline transforms implement each persona from
`prompts/user_simulator.py`; with `--use-llm` the turns are additionally
paraphrased by gpt-4o-mini (cached). Output feeds eval_adversarial.py.

    python scripts/simulate_user.py --personas all --n 30 \
        --out data/adversarial_conversations.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from gaucho_agent.prompts.user_simulator import PERSONA_NAMES
from gaucho_agent.services.eval_runner import load_probes

_EXTRA_NOISE = [
    "By the way, I like the color blue.",
    "My dorm faces east.",
    "I had cereal for breakfast.",
    "The quad was crowded today.",
    "I might get a new laptop sticker.",
    "I jog on weekends sometimes.",
]

_PARAPHRASE = [
    ("Can you suggest what I should get for dinner", "Remind me what works for my evening meal"),
    ("Which class did I say", "What course did I mention"),
    ("Who is my advisor now", "Remind me who I'm advised by these days"),
    ("safe for me", "okay given my situation"),
]


def _apply(persona: str, probe: dict, rng: random.Random) -> dict:
    p = json.loads(json.dumps(probe))  # deep copy
    p["persona"] = persona

    if persona == "contradictory":
        # Append a late session that flips the fact; question targets latest.
        flip = f"Actually, I lied earlier — disregard that. {p['gold_memory']} is no longer true."
        p["sessions"].append({
            "session_id": f"{p['user_id']}-flip",
            "turns": rng.sample(_EXTRA_NOISE, 2) + [flip],
        })
    elif persona == "distractor":
        for s in p["sessions"]:
            s["turns"] = s["turns"] + rng.sample(_EXTRA_NOISE, 3)
            rng.shuffle(s["turns"])
    elif persona == "paraphraser":
        q = p["question"]
        for a, b in _PARAPHRASE:
            q = q.replace(a, b)
        p["question"] = q
    return p


def build(personas: list[str], n: int, seed: int = 11) -> list[dict]:
    rng = random.Random(seed)
    base = load_probes(n=n)
    convs = []
    for persona in personas:
        for probe in base:
            convs.append(_apply(persona, probe, rng))
    return convs


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate adversarial conversations")
    ap.add_argument("--personas", default="all")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", default="data/adversarial_conversations.json")
    args = ap.parse_args()

    personas = (list(PERSONA_NAMES) if args.personas == "all"
                else args.personas.split(","))
    convs = build(personas, args.n, args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(convs, indent=2))
    by = {}
    for c in convs:
        by[c["persona"]] = by.get(c["persona"], 0) + 1
    print(f"wrote {len(convs)} conversations -> {out}")
    print("by persona:", dict(sorted(by.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
