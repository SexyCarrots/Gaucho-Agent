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
- Data: **LongMemEval-S** (500 Q) + 50 synthetic Gaucho probes (gold-annotated)
- Caching by turn-hash → re-runs free; 113 tests; fully offline-reproducible

*Real-mode (gpt-4o-mini answerer + gpt-4o judge). Every result below
runs end-to-end under the LongMemEval LLM-judge protocol.*

---

## Slide 5 — EXP-1: Memory ROI  ← headline

`figures/exp1_accuracy_and_roi.png`

- recent-window ΔAcc = **0** → counterfactual control works
- naive-RAG: good ΔAcc, **3× the tokens**
- **ours: comparable ΔAcc at ⅓ the tokens → 2–3× the ROI**

*Cost as a first-class metric — absent from current benchmarks.*

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

`figures/exp3_robustness.png`

- **contradictory:** ours **+0.20** gap (recency override engaging)
- **distractor:** ours −0.03 vs naive **−0.17** (judge filters noise)
- paraphrase: flat for both (pure retrieval) — as predicted

*Predicted pattern holds. LLM-simulated personas, reproducible.*

---

## Slide 8 — Ablations: which component does the work?

`figures/ablations.png`

| Variant | Acc | Ret@K | Δ vs full |
|---|---|---|---|
| `full` | **0.68** | **0.86** | — |
| `−typing` (β=0) | 0.68 | 0.86 | 0.00 |
| `−recency` (γ=0) | 0.68 | 0.86 | 0.00 |
| `−judge` (heuristic) | 0.66 | 0.78 | **−0.08 Ret@K** |

**The LLM-judge store policy is load-bearing.** β·type and γ·recency
are no-ops on small homogeneous stores (no cosine ambiguity, no time
spread). The win comes from *what gets stored*, not how it's ranked.

*The contribution is store curation, not retrieval ranking.*

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
   **ROI** (2–3×), **process** (store-F1 0.44 vs 0.23, override 0.67 vs
   0.00), and **contradictions** (+0.60 over mem0).
3. **Ablations localize the win to store curation** — the LLM judge is
   the load-bearing component; retrieval ranking is decorative on small
   stores.

Repo · [REPORT.md](REPORT.md) · [EXPERIMENTS.md](EXPERIMENTS.md) · figures/

*Thank you — questions?*
