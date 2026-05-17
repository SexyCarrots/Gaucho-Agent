"""EXP-1: Counterfactual ΔAccuracy + Memory ROI (EXPERIMENT_PLAN.md §7.1).

Each system is run with_memory and no_memory; per-category ΔAccuracy and
Memory ROI (accuracy points per 1K added prompt tokens) isolate memory's
actual contribution from the generator's baseline competence.

    python scripts/eval_counterfactual.py --n 100 \
        --systems recent_window,naive_rag,mem0,ours
"""

from __future__ import annotations

import argparse
from collections import defaultdict

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


def run_system(system: str, probes: list[dict], judge_model: str):
    """Return per-category dict: cat -> {with:[bool], no:[bool], dtok:[int]}."""
    agg = defaultdict(lambda: {"with": [], "no": [], "dtok": []})
    for probe in probes:
        cat = probe["category"]
        # with_memory
        with fresh_session() as s:
            try:
                b = get_backend(system, session=s)
            except RuntimeError as exc:           # e.g. mem0 not installed
                print(f"  [skip {system}] {exc}")
                return None
            ingest_probe(b, probe, s)
            r = answer_probe(b, probe, s, mode="with_memory")
            score_answer(s, probe, r, judge_model=judge_model)
            agg[cat]["with"].append(r.correct)
            agg[cat]["dtok"].append(r.mem_tokens)
        # no_memory (counterfactual: memory layer disabled)
        with fresh_session() as s:
            b = get_backend(system, session=s)
            r0 = answer_probe(b, probe, s, mode="no_memory")
            score_answer(s, probe, r0, judge_model=judge_model)
            agg[cat]["no"].append(r0.correct)
    return agg


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description="EXP-1 counterfactual")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--systems", default="recent_window,naive_rag,ours")
    ap.add_argument("--judge-model", default="gpt-4o")
    ap.add_argument("--out", default="results/exp1_counterfactual.csv")
    ap.add_argument("--offline", action="store_true",
                    help="force offline proxy (no network, reproducible)")
    args = ap.parse_args()

    if args.offline:
        set_offline(True)
    probes = load_probes(n=args.n)
    rows = []
    for system in args.systems.split(","):
        agg = run_system(system, probes, args.judge_model)
        if agg is None:
            continue
        for cat, d in sorted(agg.items()):
            acc_w, acc_n = _mean(d["with"]), _mean(d["no"])
            d_acc = acc_w - acc_n
            d_tok = _mean(d["dtok"])
            roi = (d_acc / (d_tok / 1000.0)) if d_tok > 0 else 0.0
            rows.append({
                "system": system, "category": cat, "n": len(d["with"]),
                "acc_with": round(acc_w, 4), "acc_no": round(acc_n, 4),
                "delta_acc": round(d_acc, 4),
                "mean_delta_tokens": round(d_tok, 2),
                "memory_roi": round(roi, 4),
            })
            print(f"{system:14s} {cat:16s} Δacc={d_acc:+.3f} "
                  f"Δtok={d_tok:6.1f} ROI={roi:+.3f}")

    write_csv(args.out, rows)
    print(f"\nwrote {len(rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
