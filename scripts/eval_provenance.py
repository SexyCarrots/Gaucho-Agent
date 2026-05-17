"""EXP-5: Memory provenance — right answer for the right reason? (§7.5).

For each correct answer, decide whether it actually used the gold-relevant
memory. Splits correct answers into provenance / lucky-guess /
distracted-right.

    python scripts/eval_provenance.py --systems recent_window,naive_rag,ours --offline
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


def main() -> int:
    ap = argparse.ArgumentParser(description="EXP-5 provenance")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--systems", default="recent_window,naive_rag,ours")
    ap.add_argument("--judge-model", default="gpt-4o")
    ap.add_argument("--out", default="results/exp5_provenance.csv")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    if args.offline:
        set_offline(True)
    probes = load_probes(n=args.n)
    rows = []

    for system in args.systems.split(","):
        n_corr = prov = lucky = distracted = 0
        for probe in probes:
            with fresh_session() as s:
                try:
                    b = get_backend(system, session=s)
                except RuntimeError as exc:
                    print(f"  [skip {system}] {exc}")
                    n_corr = -1
                    break
                ingest_probe(b, probe, s)
                r = answer_probe(b, probe, s, mode="with_memory")
                score_answer(s, probe, r, judge_model=args.judge_model)
                if not r.correct:
                    continue
                n_corr += 1
                used_gold = gold_in(probe, r.retrieved)
                if used_gold:
                    prov += 1
                else:
                    lucky += 1
                    if r.retrieved:        # had memories, just the wrong ones
                        distracted += 1
        if n_corr < 0:
            continue
        denom = n_corr or 1
        rows.append({
            "system": system, "n_correct": n_corr,
            "provenance_accuracy": round(prov / denom, 4),
            "lucky_guess_rate": round(lucky / denom, 4),
            "distracted_right_rate": round(distracted / denom, 4),
        })
        print(f"{system:14s} correct={n_corr:3d} "
              f"prov={prov/denom:.3f} lucky={lucky/denom:.3f} "
              f"distracted={distracted/denom:.3f}")

    write_csv(args.out, rows)
    print(f"wrote {len(rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
