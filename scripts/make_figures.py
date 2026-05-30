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
    """Two-panel EXP-1 figure: ΔAccuracy (left) and Memory ROI (right).

    ΔAccuracy alone hides our central claim — that `ours` matches the
    naive RAG ΔAccuracy at a fraction of the tokens. The right panel
    surfaces that as Memory ROI (accuracy points per 1K added tokens).
    """
    p = _have("exp1_counterfactual.csv")
    if not p:
        return
    df = pd.read_csv(p)
    cats = sorted(df["category"].unique())
    systems = list(df["system"].unique())
    x = range(len(cats))
    w = 0.8 / max(len(systems), 1)

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(14, 5))
    for i, s in enumerate(systems):
        sub = df[df.system == s].set_index("category").reindex(cats)
        axL.bar([xi + i * w for xi in x], sub["delta_acc"], w, label=s)
        axR.bar([xi + i * w for xi in x], sub["memory_roi"], w, label=s)

    for ax, ylabel, title in [
        (axL, "ΔAccuracy (with − no memory)",
         "Accuracy lift by category"),
        (axR, "Memory ROI (acc-pts per 1K added tokens)",
         "Token-efficiency: accuracy bought per 1K tokens"),
    ]:
        ax.set_xticks([xi + w * (len(systems) - 1) / 2 for xi in x])
        ax.set_xticklabels(cats, rotation=20, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.axhline(0, color="k", lw=0.6)
        ax.legend(loc="upper right")
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("EXP-1: Counterfactual ΔAccuracy + Memory ROI",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(dpi=200, fname=FIG / "exp1_accuracy_and_roi.png")
    print("wrote figures/exp1_accuracy_and_roi.png")

    # Companion table to stdout — useful for the report appendix.
    print(df[["system", "category", "delta_acc",
              "mean_delta_tokens", "memory_roi"]]
          .to_string(index=False))


def fig2_pareto():
    p = _have("exp2_budget_sweep.csv")
    if not p:
        return
    # K column mixes ints and "inf"; force string read so pandas doesn't
    # silently coerce "inf" to float infinity (which turns "8" into "8.0"
    # and breaks any string mapping).
    df = pd.read_csv(p, dtype={"K": str})

    def _kx(v):
        s = str(v).strip().lower().replace(".0", "")
        if s in ("inf", "infinity"):
            return 256                      # plot anchor for "unbounded"
        try:
            return int(float(s))
        except ValueError:
            return None

    fig, ax = plt.subplots(figsize=(7, 5))
    for s in df["system"].unique():
        sub = df[df.system == s].copy()
        sub["kx"] = sub["K"].apply(_kx)
        sub = sub.dropna(subset=["kx"]).sort_values("kx")
        ax.plot(sub["kx"], sub["accuracy"], marker="o", label=s)
    ax.set_xscale("log")
    ax.set_xticks([8, 32, 128, 256])
    ax.set_xticklabels(["8", "32", "128", "inf"])
    ax.axvline(32, color="grey", ls="--", lw=0.8, label="K=32")
    ax.set_xlabel("memory budget K")
    ax.set_ylabel("accuracy")
    ax.set_title("EXP-2: Memory-budget Pareto")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(dpi=200, fname=FIG / "exp2_pareto.png")
    print("wrote figures/exp2_pareto.png")


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
    fig.savefig(dpi=200, fname=FIG /"exp3_robustness.png")
    print("wrote figures/exp3_robustness.png")


def fig4_process():
    p = _have("exp4_process_metrics.csv")
    if not p:
        return
    df = pd.read_csv(p)
    metrics = ["store_f1", "retrieve_f1", "override_precision"]
    # Hide systems whose pipeline is structurally inactive (all zeros).
    # The no-memory control is already validated by EXP-1's Δacc=0; here
    # it would just be an empty bar that distracts from the naive-vs-ours
    # contrast. The CSV still carries the full row for the audit trail.
    df = df[df[metrics].abs().sum(axis=1) > 0].reset_index(drop=True)
    systems = list(df["system"])
    y = range(len(systems))
    h = 0.25
    fig, ax = plt.subplots(figsize=(8, 3.5))
    for k, m in enumerate(metrics):
        ax.barh([yi + k * h for yi in y], df[m], h, label=m)
    ax.set_yticks([yi + h for yi in y])
    ax.set_yticklabels(systems)
    ax.set_xlabel("score")
    ax.set_title("EXP-4: Process-level F1 by stage")
    ax.grid(axis="x", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(dpi=200, fname=FIG / "exp4_process_f1.png")
    print("wrote figures/exp4_process_f1.png")


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
    fig.savefig(dpi=200, fname=FIG /"exp5_provenance.png")
    print("wrote figures/exp5_provenance.png")


def fig_ablations():
    """Component ablations on `ours`: full vs -typing / -recency / -judge."""
    p = _have("ablations.csv")
    if not p:
        return
    df = pd.read_csv(p)
    variants = list(df["variant"])
    x = range(len(variants))
    w = 0.38
    fig, ax = plt.subplots(figsize=(8, 4.2))
    bars_acc = ax.bar([xi - w / 2 for xi in x], df["accuracy"], w,
                       label="accuracy", color="C0")
    bars_ret = ax.bar([xi + w / 2 for xi in x], df["retrieve_at_k"], w,
                       label="retrieve@k", color="C1")
    for b in list(bars_acc) + list(bars_ret):
        ax.annotate(f"{b.get_height():.2f}",
                    xy=(b.get_x() + b.get_width() / 2, b.get_height()),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels(variants)
    ax.set_ylabel("score")
    # Auto-zoom around the data so small effects are visible. The dashed
    # `full` reference line anchors the eye, so the non-zero baseline
    # doesn't mislead — it amplifies the contrast that matters.
    lo = min(df["accuracy"].min(), df["retrieve_at_k"].min())
    hi = max(df["accuracy"].max(), df["retrieve_at_k"].max())
    pad = max(0.04, (hi - lo) * 0.25)
    ax.set_ylim(max(0.0, lo - pad), min(1.0, hi + pad))
    ax.set_title("Ablations on `ours` (K=2: retrieval cap binds)")
    full_acc = df.loc[df.variant == "full", "accuracy"].iloc[0]
    full_ret = df.loc[df.variant == "full", "retrieve_at_k"].iloc[0]
    ax.axhline(full_acc, color="C0", ls="--", lw=0.7,
               label=f"full acc ({full_acc:.2f})")
    ax.axhline(full_ret, color="C1", ls="--", lw=0.7,
               label=f"full ret@k ({full_ret:.2f})")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(dpi=200, fname=FIG / "ablations.png")
    print("wrote figures/ablations.png")


def main() -> int:
    fig1_counterfactual()
    # EXP-2 is deferred to the LongMemEval-S real-mode run (the cap does
    # not bind on synthetic probes). Re-enable by uncommenting:
    # fig2_pareto()
    fig3_adversarial()
    fig4_process()
    # EXP-5 deferred to the LongMemEval-S real-mode run (the synthetic
    # probes pin provenance at 1.00 by construction). Re-enable with:
    # fig5_provenance()
    fig_ablations()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
