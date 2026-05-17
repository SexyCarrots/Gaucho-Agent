"""EXP-4: Process-level forensics — store / retrieve / override F1 (§7.4).

Decomposes terminal accuracy into the three latent stages so a bad number
is diagnosable: did we store it? retrieve it? override correctly?

    python scripts/eval_process_metrics.py --systems ours,naive_rag,recent_window --offline
"""

from __future__ import annotations

import argparse
from collections import defaultdict

from sqlmodel import select

from gaucho_agent.models.memory import MemoryItem
from gaucho_agent.services.eval_runner import (
    answer_probe,
    fresh_session,
    gold_match,
    load_probes,
    set_offline,
    write_csv,
)
from gaucho_agent.services.memory_backend import get_backend


def _f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description="EXP-4 process metrics")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--systems", default="ours,naive_rag,recent_window")
    ap.add_argument("--out", default="results/exp4_process_metrics.csv")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    if args.offline:
        set_offline(True)
    probes = load_probes(n=args.n)
    rows = []

    for system in args.systems.split(","):
        m = defaultdict(list)
        ov_fired = ov_correct = 0
        for probe in probes:
            with fresh_session() as s:
                try:
                    b = get_backend(system, session=s)
                except RuntimeError as exc:
                    print(f"  [skip {system}] {exc}")
                    m = None
                    break
                stored = []
                for sess in probe["sessions"]:
                    for i, turn in enumerate(sess["turns"]):
                        it = b.store(s, turn, user_id=probe["user_id"],
                                     session_id=sess["session_id"],
                                     source_turn_idx=i)
                        if it is not None:
                            stored.append(it.content)
                total_turns = sum(len(x["turns"]) for x in probe["sessions"])

                # --- store F1 (1 needle = total_relevant) ---
                rel = sum(1 for c in stored if gold_match(probe, c))
                sp = rel / len(stored) if stored else 0.0
                sr = 1.0 if rel >= 1 else 0.0
                m["store_p"].append(sp)
                m["store_r"].append(sr)
                m["store_f1"].append(_f1(sp, sr))
                m["storage_rate"].append(
                    len(stored) / total_turns if total_turns else 0.0)

                # --- retrieve F1 ---
                r = answer_probe(b, probe, s, mode="with_memory")
                rret = sum(1 for c in r.retrieved if gold_match(probe, c))
                rp = rret / len(r.retrieved) if r.retrieved else 0.0
                rr = 1.0 if rret >= 1 else 0.0
                m["retrieve_at_k"].append(rr)
                m["retrieve_f1"].append(_f1(rp, rr))

                # --- override precision (knowledge_update only) ---
                if probe["category"] == "knowledge_update":
                    superseded = s.exec(
                        select(MemoryItem).where(
                            MemoryItem.user_id == probe["user_id"],
                            MemoryItem.superseded_by != None,  # noqa: E711
                        )
                    ).all()
                    if superseded:
                        ov_fired += 1
                        if gold_match(probe, " ".join(r.retrieved)):
                            ov_correct += 1
        if m is None:
            continue

        def mean(key):
            return round(sum(m[key]) / len(m[key]), 4) if m[key] else 0.0

        ov_prec = round(ov_correct / ov_fired, 4) if ov_fired else 0.0
        rows.append({
            "system": system, "n": len(probes),
            "store_precision": mean("store_p"),
            "store_recall": mean("store_r"),
            "store_f1": mean("store_f1"),
            "retrieve_at_k": mean("retrieve_at_k"),
            "retrieve_f1": mean("retrieve_f1"),
            "override_precision": ov_prec,
            "overrides_fired": ov_fired,
            "storage_rate": mean("storage_rate"),
        })
        print(f"{system:14s} storeF1={mean('store_f1'):.3f} "
              f"retF1={mean('retrieve_f1'):.3f} "
              f"ovP={ov_prec:.3f} rate={mean('storage_rate'):.3f}")

    write_csv(args.out, rows)
    print(f"wrote {len(rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
