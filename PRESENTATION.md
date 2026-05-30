# Presentation — Selective Memory: A Multi-Axis Evaluation Framework

6-minute talk, 10 slides (~35 s each). Figures live in `figures/`.
Speaker notes in *italics*. Full detail: [REPORT.md](REPORT.md).

---

## Slide 1 — Title

**Selective Memory for LLM Agents — and how to actually evaluate it**

Gaucho-Agent · 2-week solo build · 113 tests green

*The system is unambitious on purpose. The evaluation is the research.*

---

## Slide 2 — The problem

Memory papers report **one number**: "X% on benchmark Y."

That conflates four questions:

1. Did it **store** the right thing?
2. Did it **retrieve** it?
3. Did it **use** it?
4. Was the **cost** worth it?

*One number can't tell you which of these broke. That's the gap.*

---

## Slide 3 — Contribution

A **three-axis evaluation framework** — one experiment per question:

| Axis | Question | Metric |
|---|---|---|
| EXP-1 | accuracy vs cost | Memory ROI |
| EXP-3 | messy users | Robustness gap |
| EXP-4 | which stage fails | Store/Retrieve/Override F1 |

*Lets us say "X wins on Y because Z" — not "X is 3 points better."*

---

## Slide 4 — System & setup

- Backends behind one interface: **recent-window · naive-RAG · mem0 · ours**
- **ours** = LLM-judge store + `α·cos + β·type + γ·recency` + recency override
- Data: **synthetic Gaucho probes** (50, gold-annotated); LongMemEval-S harness wired for budget-permitting scaling
- Caching by turn-hash → re-runs free; 113 tests; fully offline-reproducible

*Real-mode (gpt-4o-mini answerer + gpt-4o judge). Every result below
runs end-to-end under the LongMemEval LLM-judge protocol.*

---

## Slide 5 — EXP-1: Memory ROI  ← headline

`figures/exp1_accuracy_and_roi.png` · n=40/category

- recent-window ΔAcc = **0** → counterfactual control works
- naive-RAG: ΔAcc 0.70–0.75, but pays **46–73 added tokens** → ROI 10–16
- **ours: ΔAcc 0.63–0.73 at ~half the tokens (26–35) → ROI 18–28**

*ours trades ~5 pts of ΔAcc for ~half the prompt cost, yielding ~2×
the Memory ROI — cost as a first-class metric.*

---

## Slide 6 — EXP-4: Process forensics  ← most novel

`figures/exp4_process_f1.png`

| | Store-F1 | Override-prec | Storage-rate |
|---|---|---|---|
| **ours** | **0.44** | **0.67** | 0.38 |
| naive | 0.23 | 0.00 | 1.00 (stores everything) |

*This diagnoses **why** naive's accuracy is fragile. No paper reports
store-F1 or override-precision — memory is treated as a black box.*

---

## Slide 7 — EXP-3: Adversarial robustness

`figures/exp3_robustness.png` · ours vs mem0, n=30/persona

- **contradictory:** ours **0.90** (+0.23 gap), mem0 **0.40** (−0.37 gap)
  → **+0.50 absolute / +0.60 in gap** — the recency override engaging
- **distractor:** ours 0.63 (−0.03), mem0 0.77 (0.00) — mem0 wins
- **paraphrase:** both 0.67 vs 0.77, both gap 0.00 — tie (pure retrieval)

*ours dominates where structural overrides matter (contradictions);
mem0 holds on lexical noise. Per-persona separation a single number
would have averaged away.*

---

## Slide 8 — Ablations: which component does the work?

`figures/ablations.png` · n=50, K=2 (cap binds)

| Variant | Acc | Ret@K | Δ vs `full` |
|---|---|---|---|
| `full` | 0.40 | **0.56** | — |
| `−typing` (β=0) | 0.38 | **0.48** | **−0.08 Ret@K** |
| `−recency` (γ=0) | 0.42 | 0.60 | noise |
| `−judge` (heuristic) | **0.46** | 0.58 | **+0.06 acc** |

**β·typing is the load-bearing retrieval term** — pulls the gold memory
into top-2 under a tight cap. γ·recency is decorative (no time spread
in single-shot eval). **Store curation is a budget-regime tradeoff** —
the judge wins at K=8 but loses at K=2 (canonical normalization is
lossy when the cap forces hard choices).

*Single-K ablations hide this. The multi-axis instrument finds it.*

---

## Slide 9 — Scaling out

- Same harness, same commands — drop the `--n` cap
- LongMemEval-S real-mode run (~12M + ~1M tokens, harness ready)
- β·type and γ·recency expected to surface there (cosine ambiguity +
  multi-day haystacks)

*Caching by turn-hash → re-runs are free. The framework is done; the
remaining gate is token budget.*

---

## Slide 10 — Takeaways

1. Single-number memory eval **hides** store/retrieve/use/cost.
2. The three-axis framework makes claims **diagnostic**: ours wins on
   **ROI** (~2× naive at ~half the tokens), **process** (store-F1
   0.44 vs 0.23, override-prec 0.67 vs 0.00), and **contradictions**
   (+0.60 gap over mem0).
3. **Ablations under a binding retrieval cap** show β·typing carrying
   the retrieval load (−0.08 Ret@K when removed) and reveal store
   curation as a *budget-regime tradeoff* — a finding a single-K
   ablation would have hidden.

Repo · [REPORT.md](REPORT.md) · [EXPERIMENTS.md](EXPERIMENTS.md) · figures/

*Thank you — questions?*
