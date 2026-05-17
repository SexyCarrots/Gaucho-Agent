"""Day-6: LongMemEval-S benchmark driver (§5 Day 6, §10).

Runs every backend over LongMemEval-S via the shared eval harness and
writes per-(system,category) accuracy. Defaults to a 10-question
stratified smoke subset -> results/smoke.csv (Day-6 "Done when").

    python scripts/download_longmemeval.py            # one-time, 278 MB
    python scripts/eval_longmemeval.py --n 10 \
        --systems recent_window,naive_rag,mem0,ours --offline

If the dataset is not downloaded, falls back to the synthetic probe set
with a clear warning so the pipeline still produces numbers.
"""

from __future__ import annotations

import argparse
from collections import defaultdict

from gaucho_agent.services import longmemeval
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


def _load(n: int):
    if longmemeval.is_available():
        print(f"LongMemEval-S: {longmemeval.DEFAULT_PATH}")
        return longmemeval.load_longmemeval_s(n=n, stratified=True), "longmemeval_s"
    print("WARNING: LongMemEval-S not found "
          "(run scripts/download_longmemeval.py). "
          "Falling back to synthetic probes.")
    return load_probes(n=n), "synthetic_fallback"


def main() -> int:
    ap = argparse.ArgumentParser(description="LongMemEval-S driver")
    ap.add_argument("--n", type=int, default=10, help="stratified subset size")
    ap.add_argument("--systems",
                    default="recent_window,naive_rag,ours")
    ap.add_argument("--judge-model", default="gpt-4o")
    ap.add_argument("--out", default="results/smoke.csv")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    if args.offline:
        set_offline(True)
    probes, source = _load(args.n)
    print(f"source={source}  n={len(probes)}  "
          f"systems={args.systems}\n")

    rows = []
    for system in args.systems.split(","):
        per_cat = defaultdict(list)
        overall = []
        for p in probes:
            with fresh_session() as s:
                try:
                    b = get_backend(system, session=s)
                except RuntimeError as exc:
                    print(f"  [skip {system}] {exc}")
                    overall = None
                    break
                ingest_probe(b, p, s)
                r = answer_probe(b, p, s, mode="with_memory")
                score_answer(s, p, r, judge_model=args.judge_model)
                per_cat[p["category"]].append(r.correct)
                overall.append(r.correct)
        if overall is None:
            continue
        acc = sum(overall) / len(overall) if overall else 0.0
        rows.append({"system": system, "category": "ALL",
                     "n": len(overall), "accuracy": round(acc, 4),
                     "source": source})
        print(f"{system:14s} ALL  acc={acc:.3f}  (n={len(overall)})")
        for cat, xs in sorted(per_cat.items()):
            a = sum(xs) / len(xs) if xs else 0.0
            rows.append({"system": system, "category": cat,
                         "n": len(xs), "accuracy": round(a, 4),
                         "source": source})
            print(f"{system:14s} {cat:24s} acc={a:.3f} (n={len(xs)})")

    write_csv(args.out, rows)
    print(f"\nwrote {len(rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
