"""EXP-3: Adversarial stress test (§7.3).

Runs systems over the persona-transformed conversations from
simulate_user.py and reports per-persona accuracy and the robustness gap
vs the clean baseline (same questions, untransformed probes).

    python scripts/simulate_user.py --personas all --n 30
    python scripts/eval_adversarial.py --systems ours,naive_rag \
        --in data/adversarial_conversations.json --offline
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from gaucho_agent.services.eval_runner import (
    answer_probe,
    fresh_session,
    ingest_probe,
    load_probes,
    score_answer,
    set_offline,
    write_csv,
)
from gaucho_agent.services.memory_backend import get_backend


def _acc(system: str, convs: list[dict], judge_model: str) -> float:
    hits = []
    for c in convs:
        with fresh_session() as s:
            try:
                b = get_backend(system, session=s)
            except RuntimeError as exc:
                print(f"  [skip {system}] {exc}")
                return -1.0
            ingest_probe(b, c, s)
            r = answer_probe(b, c, s, mode="with_memory")
            score_answer(s, c, r, judge_model=judge_model)
            hits.append(r.correct)
    return sum(hits) / len(hits) if hits else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description="EXP-3 adversarial")
    ap.add_argument("--systems", default="ours,naive_rag")
    ap.add_argument("--in", dest="infile",
                    default="data/adversarial_conversations.json")
    ap.add_argument("--judge-model", default="gpt-4o")
    ap.add_argument("--out", default="results/exp3_adversarial.csv")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    if args.offline:
        set_offline(True)
    convs = json.loads(Path(args.infile).read_text())
    by_persona: dict = defaultdict(list)
    for c in convs:
        by_persona[c["persona"]].append(c)

    # Clean baseline: same probes, untransformed.
    clean = load_probes(n=len({c["id"] for c in convs}))

    rows = []
    for system in args.systems.split(","):
        base = _acc(system, clean, args.judge_model)
        if base < 0:
            continue
        for persona, cs in sorted(by_persona.items()):
            acc = _acc(system, cs, args.judge_model)
            gap = acc - base
            rows.append({
                "system": system, "persona": persona, "n": len(cs),
                "accuracy": round(acc, 4),
                "clean_baseline": round(base, 4),
                "robustness_gap": round(gap, 4),
            })
            print(f"{system:10s} {persona:14s} acc={acc:.3f} "
                  f"gap={gap:+.3f}")

    write_csv(args.out, rows)
    print(f"wrote {len(rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
