"""Days 12: ablations on the EXP-1 setup (§7.6).

Quantifies what each component of `ours` contributes:
  full        – all components on
  -typing     – β = 0 (no query/type match term)
  -recency    – γ = 0 (no recency decay)
  -judge      – heuristic store policy instead of the LLM-judge

    python scripts/eval_ablations.py --n 50 --offline
"""

from __future__ import annotations

import argparse

from gaucho_agent.services.eval_runner import (
    answer_probe,
    fresh_session,
    gold_in,
    ingest_probe,
    load_probes,
    score_answer,
    set_offline,
    write_csv,
)
from gaucho_agent.services.memory_backend import get_backend

VARIANTS = {
    "full": {},
    "-typing": {"beta": 0.0},
    "-recency": {"gamma": 0.0},
    "-judge": {"use_judge": False},
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Ablations on ours")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--judge-model", default="gpt-4o")
    ap.add_argument("--out", default="results/ablations.csv")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    if args.offline:
        set_offline(True)
    probes = load_probes(n=args.n)
    rows = []

    for name, kw in VARIANTS.items():
        hits, ret_hits = [], []
        for probe in probes:
            with fresh_session() as s:
                b = get_backend("ours", session=s, **kw)
                ingest_probe(b, probe, s)
                r = answer_probe(b, probe, s, mode="with_memory")
                score_answer(s, probe, r, judge_model=args.judge_model)
                hits.append(r.correct)
                ret_hits.append(gold_in(probe, r.retrieved))
        acc = sum(hits) / len(hits) if hits else 0.0
        ratk = sum(ret_hits) / len(ret_hits) if ret_hits else 0.0
        rows.append({
            "variant": name, "n": len(probes),
            "accuracy": round(acc, 4), "retrieve_at_k": round(ratk, 4),
        })
        print(f"{name:10s} acc={acc:.3f} ret@k={ratk:.3f}")

    write_csv(args.out, rows)
    print(f"wrote {len(rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
