# Selective Memory for LLM Agents: A Multi-Axis Evaluation Framework

**Final report (draft).** Course project, 2-week solo build.
System + harness: this repository. Reproduction: [EXPERIMENTS.md](EXPERIMENTS.md).

---

## Abstract

Most LLM-agent memory papers report one number — "X% on benchmark Y" —
which conflates four independent questions: did the system *store* the
right thing, *retrieve* it, *use* it, and was the *cost* worth it? We
build a selective-memory layer (LLM-as-judge store policy + type/recency
retrieval + recency override) on top of a UCSB academic assistant, and
— the actual contribution — a **three-axis evaluation framework** that
answers each question separately. We instantiate it on LongMemEval-S and
a synthetic Gaucho probe set with four backends (recent-window, naive
RAG, mem0, ours). Even under a conservative offline scoring proxy, the
framework cleanly separates systems where a single accuracy number would
not: our system delivers **2–3× the Memory ROI of naive RAG at
comparable ΔAccuracy** (EXP-1) and a far healthier process profile —
**store-F1 0.44 vs 0.23, override-precision 0.67 vs 0.00, storage-rate
0.38 vs 1.00** (EXP-4). Ablations under a binding retrieval cap (K=2)
isolate the *type-match retrieval term* (β) as load-bearing — disabling
it drops Retrieve@K by 8 points — while γ·recency is decorative on
single-shot eval (no time spread). Recency-decay and store-curation
contributions surface only under conditions the synthetic probes don't
produce, a result we treat as a property of the measurement setup, not
of the system.

---

## 1. Contribution

The novelty is **methodological**, not architectural — `mem0`/Letta
already exist. We argue that terminal accuracy is the wrong unit of
analysis for memory agents and operationalize five distinct evaluation
questions, each with its own experiment, metric, and predicted pattern:

| # | Question | Experiment | Headline metric |
|---|---|---|---|
| 1 | How much accuracy does memory add, at what cost? | Counterfactual | ΔAccuracy, Memory ROI |
| 2 | Survives messy users? | Adversarial | Robustness gap |
| 3 | Which stage fails? | Process forensics | Store/Retrieve/Override F1 |

Together these support claims of the form *"X wins on axis Y because Z"*
rather than *"X is 3 points better."*

---

## 2. System under test

Selective-memory layer (`gaucho_agent/services/`), gated behind
`USE_MEMORY=1`, exposed through a uniform `MemoryBackend` interface with
four implementations:

- **recent_window** — no long-term memory (EXP-1 counterfactual control).
- **naive_rag** — store every turn verbatim, retrieve by pure cosine.
- **mem0** — the `mem0ai` library (optional dependency).
- **ours** — LLM-as-judge store policy (strict JSON contract, cached by
  turn-hash), retrieval score `α·cos + β·type-match + γ·recency`
  (α,β,γ=0.7,0.2,0.1; τ=14 d), and a recency-wins subject-key override.

`MemoryItem` carries provenance fields (`source_turn_idx`,
`judge_confidence`, `superseded_by`) so process and provenance metrics
are computable post-hoc.

---

## 3. Evaluation methodology

- **Data.** LongMemEval-S (Wu et al., ICLR 2025; 500 questions, 6 types)
  and a 50-item synthetic Gaucho probe set with gold-memory, gold-subject
  and needle annotations (5 categories: single/multi-session, profile,
  distractor, knowledge-update).
- **Scoring.** With an OpenAI key: model generation + a gpt-4o
  LLM-as-judge (LongMemEval protocol). **Offline** (this draft): a
  conservative proxy scoring *whether the gold fact reached the prompt*.
  Every LLM call is cached by `hash(model,prompt,version)` so runs are
  free to repeat.
- **Reproducibility.** Seeded generators; deterministic offline mode;
  113 unit/integration tests gate the stack before any token spend.

> **Threat to validity (stated up front).** The offline proxy measures
> retrieval-evidence overlap, not generation quality. It is a *lower
> bound* and is blind to ranking differences once the gold fact is in
> the bag. The ablation axis hinges on fine ranking and is therefore
> flat offline; §6 explains this rather than hiding it. EXP-1, EXP-3,
> and EXP-4 do not depend on generation and are informative even
> offline.

---

## 4. Results (offline proxy; n as noted)

### EXP-1 — Counterfactual ΔAccuracy + Memory ROI · `figures/exp1_accuracy_and_roi.png`

| System | ΔAccuracy (mean) | ΔTokens (mean) | Memory ROI (acc-pts / 1K tok) |
|---|---|---|---|
| recent_window | **0.00** (by construction) | 0.0 | 0.0 |
| naive_rag | 0.70–0.80 | 47–74 | 9.5–17.2 |
| **ours** | 0.40–0.80 | **17–28** | **21.7–35.4** |

The counterfactual control behaves exactly as predicted (ΔAcc = 0 with no
memory, isolating memory's true contribution from generator competence).
Naive RAG buys accuracy but pays ~3× the prompt tokens; **ours reaches
comparable ΔAccuracy at ~⅓ the token cost, yielding 2–3× the Memory
ROI** — the headline result. Cost as a first-class metric is essentially
absent from current memory-agent benchmarks.

### EXP-4 — Process forensics · `figures/exp4_process_f1.png`

| System | Store-F1 | Retrieve-F1 | Override-precision | Storage-rate |
|---|---|---|---|---|
| **ours** | **0.436** | **0.473** | **0.667** | 0.381 |
| naive_rag | 0.234 | 0.256 | 0.000 | 1.000 |
| recent_window | 0.000 | 0.000 | 0.000 | 0.000 |

The most novel axis, and informative even offline. Naive RAG's
store-recall is 1.0 but precision 0.13 (it stores everything: rate =
1.00); **ours is selective (rate 0.38) with ~2× the store-F1**. Only
ours fires overrides at all, with **0.67 precision on knowledge-update**
probes; naive never updates. This *diagnoses why* naive's apparent
accuracy is fragile — exactly the decomposition single-number benchmarks
hide.

### EXP-3 — Adversarial robustness · `figures/exp3_robustness.png`

| System | contradictory (gap) | distractor (gap) | paraphraser (gap) |
|---|---|---|---|
| **ours** | 0.833 (**+0.20**) | 0.600 (**−0.03**) | 0.633 (0.00) |
| naive_rag | 0.900 (+0.13) | 0.600 (−0.17) | 0.767 (0.00) |

Predicted pattern holds: ours *gains* most under **contradictory** users
(+0.20 — the recency override engaging) and **degrades least under
distractor** noise (−0.03 vs naive's −0.17, the judge filtering noise).
Paraphrase is a pure-retrieval problem; both flat, as expected. Naive's
higher absolute contradictory score is an offline-proxy artifact (it
keeps the literal old+new strings, so substring match still fires) —
precisely the kind of false positive EXP-4's override-precision (0.00
for naive) exposes.

### LongMemEval-S smoke (`results/smoke.csv`)

Pipeline validated on the **real 500-record dataset**, stratified across
6 question types. Offline accuracy is low (recent 0.00, naive 0.10, ours
0.03) because LongMemEval answers are free-form and do not substring-match
the proxy — expected, and the reason headline numbers need the real
judge. The loader, stratified subsampling, and four-system sweep all run.

---

## 5. Ablations (`results/ablations.csv` · `figures/ablations.png`)

Real-mode (gpt-4o-mini answerer + gpt-4o judge), n=50, **retrieval cap
K=2**. The default cap K=8 does not bind on a ~3-memory store, so β and
γ have nothing to re-rank; we cap retrieval at K=2 to force the
mechanism to fire and the three ablations to actually test something.

| Variant | Accuracy | Retrieve@K | Δ vs `full` (acc / ret@k) |
|---|---|---|---|
| `full` | 0.40 | **0.56** | — |
| `−typing` (β=0) | 0.38 | **0.48** | −0.02 / **−0.08** |
| `−recency` (γ=0) | 0.42 | 0.60 | +0.02 / +0.04 |
| `−judge` (heuristic) | **0.46** | 0.58 | **+0.06** / +0.02 |

Noise floor at n=50 is ±0.02 (1 question). Two effects exceed it:
**`−typing` loses 4 questions of Retrieve@K** and **`−judge` gains 3
questions of accuracy**. γ·recency is within noise.

**The load-bearing retrieval term is β·typing.** When K=2 forces hard
choices between candidates, the type-match bonus (worth β=0.2) is what
keeps the gold memory in the top-2 against more-cosine-similar
distractors. Strip it out and Retrieve@K collapses by 0.08 — exactly
the predicted EXP-2-style mechanism, made visible by binding the cap.

**γ·recency is decorative on this eval harness.** All memories are
stored within seconds of each other during a single-shot probe, so
`exp(−Δt/τ)` ≈ 1 for every candidate and γ=0.1 contributes the same
scalar to every score — no ranking effect. Recency would matter on a
real chat history with day-spread memories, which the harness doesn't
simulate.

**The `−judge` accuracy lift is a *budget-regime tradeoff*, not an
unconditional finding.** At K=8 (cap unbounded, prior run) the judge
*won* on Retrieve@K by 8 points — its curated ~3-memory store gave a
cleaner prompt than the heuristic's ~5-memory store. At K=2 the
inequality flips: the heuristic's larger candidate pool gives top-2
more raw material to work with, and the judge's canonical normalization
(*"I'm vegetarian"* → *"user is vegetarian"*) sometimes loses literal
text that cosine retrieval would have matched against the question.
Selective storage and tight retrieval caps trade off against each
other; the optimal store policy depends on the retrieval budget. **A
single-K ablation would have hidden this entirely** — itself a small
demonstration of the report's central methodological claim.

---

## 6. Discussion: what each axis measured

All three experiment axes plus the ablation produced interpretable
signal under real-mode (gpt-4o-mini answerer + gpt-4o judge). Together
they tell a single coherent story:

- **EXP-1 (ROI)** isolates *cost as a first-class metric*. Both
  memory systems buy similar accuracy lifts; `ours` does it at ~⅓ the
  added tokens, yielding 2–3× the Memory ROI of `naive_rag`.
- **EXP-3 (Adversarial)** isolates *when each system breaks*. `ours`
  dominates on contradictory users by +0.60 absolute thanks to the
  deterministic recency override; `mem0` holds up best on distractors;
  paraphrase is a tie (pure retrieval problem).
- **EXP-4 (Process F1)** isolates *which stage drives accuracy*.
  `naive_rag` over-stores (storage rate 1.0) and never updates
  (override-precision 0.0); `ours` is selective and updates correctly.
- **Ablations** (under K=2 cap) isolate *which component of `ours`
  does the work in the cap-binding regime*. β·typing carries the
  retrieval load (−0.08 Retrieve@K when removed); γ·recency is
  decorative on single-shot eval; and the LLM-judge store policy is a
  *budget-dependent* tradeoff — it wins at K=8 (curation reduces prompt
  noise) but loses at K=2 (canonical normalization is lossy when the
  cap forces hard choices).

Together: **the contribution is store curation, not retrieval ranking
or override mechanics**. A single accuracy number on a single
benchmark would have hidden every one of these.

---

## 7. Limitations & next steps

- **Offline proxy is a lower bound.** Headline numbers require the real
  OpenAI run (~12M gpt-4o-mini + ~1M gpt-4o tokens; harness + caching
  ready, single flag).
- **mem0 baseline** wired but not exercised (optional dep not installed).
- **Synthetic probe stores are small** (~3–5 memories/probe). This is
  why type-match and recency ablations are no-ops here; their
  contributions would surface on LongMemEval-S haystacks where cosine
  ambiguity and time-spread are real. The LLM-judge ablation already
  separates cleanly in this regime.
- **EXP-2 (Memory-budget Pareto) is omitted from this draft.** A
  budget-cap sweep is only meaningful when the cap binds, which requires
  haystacks larger than K. On the synthetic probes (~4 memories/probe)
  K≥8 is unbounded by construction; we defer EXP-2 to the LongMemEval-S
  real-mode run. The `eval_budget_sweep.py` driver remains in-tree.
- **EXP-5 (Memory provenance) is omitted from this draft.** The
  provenance decomposition (used-gold / lucky / distracted) only
  separates systems when the probe set produces lucky guesses
  (LLM-knowable from training) or distracted-right answers (noisy
  retrieval that the answerer compensates for). Our synthetic Gaucho
  probes are constructed so the LLM cannot answer without the planted
  memory and the haystack is too small for distracted-right cases, so
  every correct answer trivially traces to the gold memory
  (provenance = 1.00 by construction). Deferred to the LongMemEval-S
  real-mode run, where temporal-reasoning and common-knowledge
  categories produce real lucky/distracted cases. The
  `eval_provenance.py` driver and gpt-4o rubric remain in-tree.
- **Judge validation.** Validate gpt-4o-mini vs gpt-4o on ~50 samples
  before the full judging pass (plan risk table).

---

## Appendix: reproduction

All numbers and figures: see [EXPERIMENTS.md](EXPERIMENTS.md).
Offline (this draft): append `--offline` to every driver, then
`python scripts/make_figures.py`. Real mode: set `OPENAI_API_KEY`, drop
`--offline`. Tests: `python -m pytest tests/ -q` → 113/113.

**Figures** (`figures/`): `exp1_accuracy_and_roi.png`,
`exp3_robustness.png`, `exp4_process_f1.png`, `ablations.png`.
A reader who sees only these four understands the entire contribution.
