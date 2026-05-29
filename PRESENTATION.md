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

A **four-axis evaluation framework** — one experiment per question:

| Axis | Question | Metric |
|---|---|---|
| EXP-1 | accuracy vs cost | Memory ROI |
| EXP-3 | messy users | Robustness gap |
| EXP-4 | which stage fails | Store/Retrieve/Override F1 |
| EXP-5 | right reasons | Provenance accuracy |

*Lets us say "X wins on Y because Z" — not "X is 3 points better."*

---

## Slide 4 — System & setup

- Backends behind one interface: **recent-window · naive-RAG · mem0 · ours**
- **ours** = LLM-judge store + `α·cos + β·type + γ·recency` + recency override
- Data: **LongMemEval-S** (500 Q) + 50 synthetic Gaucho probes (gold-annotated)
- Caching by turn-hash → re-runs free; 113 tests; fully offline-reproducible

*Honest caveat up front: this draft uses a conservative offline proxy —
a lower bound. The ablation axis goes flat under it; I'll show that's a
finding.*

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

## Slide 8 — When "flat" is a finding

The **ablation** axis (−typing / −recency / −judge) is **flat offline**.

Not hidden — explained: synthetic stores have ~4 memories, and an
offline judge already reduces to the heuristic, so β/γ/judge toggles
rarely flip whether the gold fact is retrieved.

*A multi-axis instrument tells you which axis your setup can resolve.
One averaged number would have buried this.*

---

## Slide 9 — What real-mode adds

- Same commands, drop `--offline`, set `OPENAI_API_KEY`
- Generation + **gpt-4o LLM-judge** (LongMemEval protocol)
- Surfaces ablation contributions (β·type, γ·recency, judge)
- Surfaces EXP-5 lucky/distracted answers
- Budget: ~12M + ~1M tokens; harness + caching already in place

*Zero code change. The framework is done; the spend is the only gate.*

---

## Slide 10 — Takeaways

1. Single-number memory eval **hides** store/retrieve/use/cost.
2. A 5-axis framework makes claims **diagnostic**: ours wins on **ROI**
   (2–3×) and **process** (store-F1 0.44 vs 0.23, override 0.67 vs 0.00).
3. **Negative/flat results are informative** — they localize the
   measurement, not just the system.

Repo · [REPORT.md](REPORT.md) · [EXPERIMENTS.md](EXPERIMENTS.md) · figures/

*Thank you — questions?*
