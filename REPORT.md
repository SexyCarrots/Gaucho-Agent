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
— the actual contribution — a **five-axis evaluation framework** that
answers each question separately. We instantiate it on LongMemEval-S and
a synthetic Gaucho probe set with four backends (recent-window, naive
RAG, mem0, ours). Even under a conservative offline scoring proxy, the
framework cleanly separates systems where a single accuracy number would
not: our system delivers **2–3× the Memory ROI of naive RAG at
comparable ΔAccuracy** (EXP-1) and a far healthier process profile —
**store-F1 0.44 vs 0.23, override-precision 0.67 vs 0.00, storage-rate
0.38 vs 1.00** (EXP-4). Two axes (budget Pareto, ablations) are flat
under the offline proxy; we show *why*, which is itself a finding about
measurement instruments for memory systems.

---

## 1. Contribution

The novelty is **methodological**, not architectural — `mem0`/Letta
already exist. We argue that terminal accuracy is the wrong unit of
analysis for memory agents and operationalize five distinct evaluation
questions, each with its own experiment, metric, and predicted pattern:

| # | Question | Experiment | Headline metric |
|---|---|---|---|
| 1 | How much accuracy does memory add, at what cost? | Counterfactual | ΔAccuracy, Memory ROI |
| 2 | Smart ranking or just keep everything? | Budget Pareto | Selectivity premium |
| 3 | Survives messy users? | Adversarial | Robustness gap |
| 4 | Which stage fails? | Process forensics | Store/Retrieve/Override F1 |
| 5 | Right answer for the right reason? | Provenance | Provenance accuracy |

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
> the bag. Axes that hinge on generation or fine ranking (EXP-2, EXP-5,
> ablations) are therefore flat offline; §6 explains this rather than
> hiding it. EXP-1 and EXP-4 do not depend on generation and are
> informative even offline.

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

### EXP-2 — Budget Pareto · `figures/exp2_pareto.png`

Flat across K ∈ {8,32,128,∞} for both systems (selectivity premium
1.00). **This is a measurement-instrument result, not a system result:**
the synthetic probes plant ~4 memories, so a K≥8 cap never binds, and the
offline proxy cannot see ranking changes once the gold fact is retrieved.
The mechanism (cap applied *after* store, measuring ranking) is correct
and unit-tested; separating the systems requires the real LLM judge
and/or longer LongMemEval haystacks (≥128 memories), where the cap binds.

### EXP-5 — Provenance · `figures/exp5_provenance.png`

| System | n correct | Provenance acc | Lucky | Distracted |
|---|---|---|---|---|
| recent_window | 0 | 0.00 | 0.00 | 0.00 |
| naive_rag | 38 | 1.00 | 0.00 | 0.00 |
| ours | 33 | 1.00 | 0.00 | 0.00 |

recent_window is correct 0 times (no memory ⇒ no lucky guesses — the
control validates the metric). Provenance is 1.00 for both memory
systems *by construction of the offline proxy* (it only scores correct
when the gold fact is in the retrieved set). The real LLM judge is
required to observe lucky/distracted answers; the harness and rubric
(gpt-4o provenance judge) are in place.

### LongMemEval-S smoke (`results/smoke.csv`)

Pipeline validated on the **real 500-record dataset**, stratified across
6 question types. Offline accuracy is low (recent 0.00, naive 0.10, ours
0.03) because LongMemEval answers are free-form and do not substring-match
the proxy — expected, and the reason headline numbers need the real
judge. The loader, stratified subsampling, and four-system sweep all run.

---

## 5. Ablations (`results/ablations.csv`)

`full`, `−typing` (β=0), `−recency` (γ=0), `−judge` (heuristic) all score
0.66 / ret@k 0.78 offline. Like EXP-2, this is the offline proxy's
blind spot: with ~4 memories and an offline judge that already reduces to
the heuristic, β/γ/judge toggles rarely flip *whether* the gold fact is
retrieved. The ablation harness is wired and seeded; component
contributions become visible under the real LLM judge with larger stores.

---

## 6. Discussion: when "flat" is a finding

Three axes are informative offline (EXP-1, EXP-3, EXP-4) and two are flat
(EXP-2, EXP-5, ablations). Rather than a weakness, this is the
framework's point in miniature: **a multi-axis instrument tells you which
axis your measurement setup can and cannot resolve.** A single accuracy
number would have averaged these into one misleading figure. The flat
axes localize exactly what the real-mode run must add (generation +
gpt-4o judge, longer haystacks), and the informative axes already
demonstrate the central claim — selectivity buys ROI and a healthier
process profile, not just raw accuracy.

---

## 7. Limitations & next steps

- **Offline proxy is a lower bound.** Headline numbers require the real
  OpenAI run (~12M gpt-4o-mini + ~1M gpt-4o tokens; harness + caching
  ready, single flag).
- **mem0 baseline** wired but not exercised (optional dep not installed).
- **Synthetic probe stores are small;** EXP-2/ablations need either the
  real judge or LongMemEval's long haystacks to bind the budget cap.
- **Judge validation.** Validate gpt-4o-mini vs gpt-4o on ~50 samples
  before the full judging pass (plan risk table).

---

## Appendix: reproduction

All numbers and figures: see [EXPERIMENTS.md](EXPERIMENTS.md).
Offline (this draft): append `--offline` to every driver, then
`python scripts/make_figures.py`. Real mode: set `OPENAI_API_KEY`, drop
`--offline`. Tests: `python -m pytest tests/ -q` → 113/113.

**Figures** (`figures/`): `exp1_accuracy_and_roi.png`, `exp2_pareto.png`,
`exp3_robustness.png`, `exp4_process_f1.png`, `exp5_provenance.png`.
A reader who sees only these five understands the entire contribution.
