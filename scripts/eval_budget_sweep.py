"""EXP-2: Memory budget Pareto + Selectivity premium (§7.2).

The store is built once per probe, then retrieval is capped at K so this
isolates *ranking quality* (not storage). Selectivity premium =
Acc(K=32) / Acc(K=∞).

    python scripts/eval_budget_sweep.py --n 50 --K 8,32,128,inf \
        --systems naive_rag,ours --offline
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


def _parse_K(spec: str) -> list[int | None]:
    out: list[int | None] = []
    for tok in spec.split(","):
        tok = tok.strip().lower()
        out.append(None if tok in ("inf", "∞") else int(tok))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="EXP-2 budget sweep")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--K", default="8,32,128,inf")
    ap.add_argument("--systems", default="naive_rag,ours")
    ap.add_argument("--judge-model", default="gpt-4o")
    ap.add_argument("--out", default="results/exp2_budget_sweep.csv")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    if args.offline:
        set_offline(True)
    Ks = _parse_K(args.K)
    probes = load_probes(n=args.n)
    rows, premium = [], {}

    for system in args.systems.split(","):
        acc_by_k: dict = defaultdict(list)
        for probe in probes:
            with fresh_session() as s:
                try:
                    b = get_backend(system, session=s)
                except RuntimeError as exc:
                    print(f"  [skip {system}] {exc}")
                    acc_by_k = None
                    break
                ingest_probe(b, probe, s)
                for K in Ks:
                    r = answer_probe(b, probe, s, mode="with_memory",
                                     k=(10**9 if K is None else K))
                    score_answer(s, probe, r, judge_model=args.judge_model)
                    acc_by_k[K].append(r.correct)
        if acc_by_k is None:
            continue
        for K in Ks:
            acc = sum(acc_by_k[K]) / len(acc_by_k[K]) if acc_by_k[K] else 0.0
            label = "inf" if K is None else K
            rows.append({"system": system, "K": label,
                         "n": len(acc_by_k[K]), "accuracy": round(acc, 4)})
            print(f"{system:10s} K={str(label):>4s} acc={acc:.3f}")
        a32 = sum(acc_by_k[32]) / len(acc_by_k[32]) if acc_by_k.get(32) else 0.0
        ainf = (sum(acc_by_k[None]) / len(acc_by_k[None])
                if acc_by_k.get(None) else 0.0)
        premium[system] = round(a32 / ainf, 4) if ainf > 0 else 0.0

    write_csv(args.out, rows)
    print("\nSelectivity premium (Acc@32 / Acc@inf):")
    for sysname, p in premium.items():
        print(f"  {sysname:10s} {p}")
    print(f"wrote {len(rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
