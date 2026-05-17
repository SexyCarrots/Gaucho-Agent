"""Generate the five headline figures from results/*.csv (§8).

    python scripts/make_figures.py

Each figure is skipped (with a message) if its CSV is missing, so this
runs at any stage of the experiment pipeline.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

RES = Path("results")
FIG = Path("figures")
FIG.mkdir(parents=True, exist_ok=True)


def _have(name: str) -> Path | None:
    p = RES / name
    if p.exists() and p.stat().st_size > 0:
        return p
    print(f"skip {name}: not found")
    return None


def fig1_counterfactual():
    p = _have("exp1_counterfactual.csv")
    if not p:
        return
    df = pd.read_csv(p)
    cats = sorted(df["category"].unique())
    systems = list(df["system"].unique())
    x = range(len(cats))
    w = 0.8 / max(len(systems), 1)
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, s in enumerate(systems):
        sub = df[df.system == s].set_index("category").reindex(cats)
        ax.bar([xi + i * w for xi in x], sub["delta_acc"], w, label=s)
    ax.set_xticks([xi + w * (len(systems) - 1) / 2 for xi in x])
    ax.set_xticklabels(cats, rotation=20, ha="right")
    ax.set_ylabel("ΔAccuracy (with − no memory)")
    ax.set_title("EXP-1: Counterfactual ΔAccuracy by category")
    ax.axhline(0, color="k", lw=0.6)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "exp1_delta_accuracy.pdf")
    print("wrote figures/exp1_delta_accuracy.pdf")
    print(df[["system", "category", "delta_acc", "memory_roi"]]
          .to_string(index=False))


def fig2_pareto():
    p = _have("exp2_budget_sweep.csv")
    if not p:
        return
    df = pd.read_csv(p)
    order = {"8": 8, "32": 32, "128": 128, "inf": 256}
    fig, ax = plt.subplots(figsize=(7, 5))
    for s in df["system"].unique():
        sub = df[df.system == s].copy()
        sub["kx"] = sub["K"].astype(str).map(order)
        sub = sub.sort_values("kx")
        ax.plot(sub["kx"], sub["accuracy"], marker="o", label=s)
    ax.set_xscale("log")
    ax.set_xticks(list(order.values()))
    ax.set_xticklabels(list(order))
    ax.axvline(32, color="grey", ls="--", lw=0.8, label="K=32")
    ax.set_xlabel("memory budget K")
    ax.set_ylabel("accuracy")
    ax.set_title("EXP-2: Memory-budget Pareto")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "exp2_pareto.pdf")
    print("wrote figures/exp2_pareto.pdf")


def fig3_adversarial():
    p = _have("exp3_adversarial.csv")
    if not p:
        return
    df = pd.read_csv(p)
    piv = df.pivot(index="persona", columns="system", values="accuracy")
    gap = df.pivot(index="persona", columns="system",
                   values="robustness_gap")
    fig, ax = plt.subplots(figsize=(7, 4))
    im = ax.imshow(piv.values, cmap="viridis", aspect="auto",
                   vmin=0, vmax=1)
    ax.set_xticks(range(len(piv.columns)))
    ax.set_xticklabels(piv.columns)
    ax.set_yticks(range(len(piv.index)))
    ax.set_yticklabels(piv.index)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            ax.text(j, i, f"{piv.values[i, j]:.2f}\n(gap {gap.values[i, j]:+.2f})",
                    ha="center", va="center", color="w", fontsize=8)
    ax.set_title("EXP-3: Adversarial accuracy (persona × system)")
    fig.colorbar(im, label="accuracy")
    fig.tight_layout()
    fig.savefig(FIG / "exp3_robustness.pdf")
    print("wrote figures/exp3_robustness.pdf")


def fig4_process():
    p = _have("exp4_process_metrics.csv")
    if not p:
        return
    df = pd.read_csv(p)
    metrics = ["store_f1", "retrieve_f1", "override_precision"]
    systems = list(df["system"])
    y = range(len(systems))
    h = 0.25
    fig, ax = plt.subplots(figsize=(8, 4))
    for k, m in enumerate(metrics):
        ax.barh([yi + k * h for yi in y], df[m], h, label=m)
    ax.set_yticks([yi + h for yi in y])
    ax.set_yticklabels(systems)
    ax.set_xlabel("score")
    ax.set_title("EXP-4: Process-level F1 by stage")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "exp4_process_f1.pdf")
    print("wrote figures/exp4_process_f1.pdf")


def fig5_provenance():
    p = _have("exp5_provenance.csv")
    if not p:
        return
    df = pd.read_csv(p)
    systems = list(df["system"])
    prov = df["provenance_accuracy"]
    lucky = df["lucky_guess_rate"]
    dist = df["distracted_right_rate"]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(systems, prov, label="used gold memory")
    ax.bar(systems, lucky, bottom=prov, label="lucky (no memory)")
    ax.bar(systems, dist, bottom=prov + lucky, label="distracted (wrong mem)")
    ax.set_ylabel("fraction of correct answers")
    ax.set_title("EXP-5: Provenance decomposition of correct answers")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "exp5_provenance.pdf")
    print("wrote figures/exp5_provenance.pdf")


def main() -> int:
    fig1_counterfactual()
    fig2_pareto()
    fig3_adversarial()
    fig4_process()
    fig5_provenance()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
