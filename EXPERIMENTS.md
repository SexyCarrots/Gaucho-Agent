# Running the Experiments & Evaluation

This is the runbook for reproducing every result and figure in the final
report and presentation. It implements
[`EXPERIMENT_PLAN.md`](EXPERIMENT_PLAN.md): a selective-memory layer for
Gaucho-Agent plus a **multi-axis evaluation framework** (five experiments,
each answering a distinct research question — not a single accuracy
number). Written-up results: [REPORT.md](REPORT.md) · deck:
[PRESENTATION.md](PRESENTATION.md).

> **TL;DR.** `pip install -e ".[eval]"` → build inputs → run the seven
> driver scripts → `python scripts/make_figures.py`. Add `--offline` for a
> reproducible no-key dry run; remove it (with an OpenAI key) for the real
> LLM-judged numbers.

---

## 0. Which Python

Use the interpreter that has `gaucho` installed:

```bash
which gaucho            # e.g. /Library/Frameworks/Python.framework/Versions/3.13/bin/gaucho
PY=$(head -1 "$(which gaucho)" | sed 's/^#!//')   # the matching python
$PY -m pytest tests/ -q                            # expect 113/113
```

Below, `python` means that interpreter.

---

## 1. One-time setup

```bash
pip install -e ".[eval]"     # pandas + matplotlib + datasets (figures, LongMemEval)
pip install -e ".[memory]"   # OPTIONAL: real mem0 baseline + MiniLM embeddings
                             #           (heavy: pulls torch). Not needed otherwise.
```

The memory system and all five experiments run **without** `[memory]` —
there is a deterministic offline embedder and an offline judge fallback,
so the entire pipeline is reproducible with no API key and no network.

---

## 2. Build the experiment inputs (once)

```bash
python scripts/build_synthetic_probes.py --n 50          # -> data/synthetic_probes.json
python scripts/simulate_user.py --personas all --n 30    # -> data/adversarial_conversations.json (EXP-3)
python scripts/download_longmemeval.py                   # -> data/longmemeval_s/ (278 MB, once; gitignored)
```

`data/synthetic_probes.json` and `data/adversarial_conversations.json`
are small and checked in; LongMemEval-S is large and gitignored.

---

## 3. Two run modes

| Mode | How | What it measures | Cost |
|---|---|---|---|
| **Offline** (default-safe) | add `--offline` to any driver | retrieval-quality proxy: did the gold fact reach the prompt? | free, no network, fully reproducible |
| **Real** | omit `--offline`, set `OPENAI_API_KEY` | LLM generation + gpt-4o LLM-as-judge (LongMemEval protocol) | ~12M gpt-4o-mini + ~1M gpt-4o tokens total |

Every LLM call is cached in the `llm_cache` SQLite table by
`hash(model, prompt, version)`, so **re-runs are free** — interrupted runs
resume without re-spending tokens.

For real mode, put this in `.env`:

```env
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

---

## 4. The five experiments

Each driver prints a summary and writes a CSV under `results/`. Run with
`--offline` first to sanity-check, then without for the report numbers.

### EXP-1 — Counterfactual ΔAccuracy + Memory ROI
*How much accuracy is memory actually contributing, and at what cost?*

```bash
python scripts/eval_counterfactual.py --n 100 \
    --systems recent_window,naive_rag,mem0,ours [--offline]
```
→ `results/exp1_counterfactual.csv` · **Figure:** `figures/exp1_delta_accuracy.pdf`
(grouped ΔAccuracy bars by category + Memory-ROI table). Run this **first**
— EXP-4 reuses its logic.

### EXP-2 — Memory-budget Pareto + Selectivity premium
*Is the system smart about ranking memories, or does it just keep everything?*

```bash
python scripts/eval_budget_sweep.py --n 50 \
    --K 8,32,128,inf --systems mem0,ours [--offline]
```
→ `results/exp2_budget_sweep.csv` · **Figure:** `figures/exp2_pareto.pdf`
(accuracy vs budget K, log-x, K=32 marker).

### EXP-3 — Adversarial stress test
*Does the agent survive contradictions, distractors, paraphrase?*

```bash
python scripts/simulate_user.py --personas all --n 30   # if not already built
python scripts/eval_adversarial.py --systems ours,mem0 \
    --in data/adversarial_conversations.json [--offline]
```
→ `results/exp3_adversarial.csv` · **Figure:** `figures/exp3_robustness.pdf`
(persona × system heatmap, annotated with robustness gap).

### EXP-4 — Process-level forensics (store / retrieve / override F1)
*Which stage actually fails when accuracy is bad?*

```bash
python scripts/eval_process_metrics.py --n 50 \
    --systems ours,naive_rag,recent_window [--offline]
```
→ `results/exp4_process_metrics.csv` · **Figure:** `figures/exp4_process_f1.pdf`
(per-system Store-F1 / Retrieve-F1 / Override-precision bars).

### EXP-5 — Memory provenance
*When it's right, is it right for the right reasons?*

```bash
python scripts/eval_provenance.py --n 100 \
    --systems recent_window,naive_rag,ours [--offline]
```
→ `results/exp5_provenance.csv` · **Figure:** `figures/exp5_provenance.pdf`
(correct answers split into used-gold / lucky / distracted).

### Ablations (report Day-12)
```bash
python scripts/eval_ablations.py --n 50 [--offline]      # -typing / -recency / -judge
```
→ `results/ablations.csv`

### LongMemEval-S benchmark (Day-6 smoke / full)
```bash
python scripts/eval_longmemeval.py --n 10 \
    --systems recent_window,naive_rag,mem0,ours [--offline]
```
→ `results/smoke.csv` (raise `--n` for the full 500-question run; the
loader stratifies across the 6 question types).

---

## 5. Generate all figures for the report/presentation

```bash
python scripts/make_figures.py
```

Produces the five headline PDFs in `figures/`. It reads whatever CSVs
exist in `results/` and skips experiments you haven't run yet, so it is
safe to run at any point. **A reader who only looks at these five figures
should understand the entire contribution** (EXPERIMENT_PLAN §8):

| Figure | Experiment | Reading |
|---|---|---|
| `exp1_delta_accuracy.pdf` | EXP-1 | memory's true contribution + ROI |
| `exp2_pareto.pdf` | EXP-2 | ranking quality under a budget |
| `exp3_robustness.pdf` | EXP-3 | resilience to messy users |
| `exp4_process_f1.pdf` | EXP-4 | which pipeline stage is the weak link |
| `exp5_provenance.pdf` | EXP-5 | trustworthiness (right for right reasons) |

---

## 6. Suggested order for a full report run

```bash
# 0. sanity (≈1 s)
python scripts/eval_counterfactual.py --n 5 --offline

# 1. inputs
python scripts/build_synthetic_probes.py --n 50
python scripts/simulate_user.py --personas all --n 30
python scripts/download_longmemeval.py

# 2. experiments (real mode: drop --offline, ensure OPENAI_API_KEY set)
python scripts/eval_counterfactual.py  --n 100 --systems recent_window,naive_rag,mem0,ours
python scripts/eval_budget_sweep.py    --n 50  --K 8,32,128,inf --systems mem0,ours
python scripts/eval_adversarial.py     --systems ours,mem0
python scripts/eval_process_metrics.py --n 50  --systems ours,naive_rag,recent_window
python scripts/eval_provenance.py      --n 100 --systems recent_window,naive_rag,ours
python scripts/eval_ablations.py       --n 50
python scripts/eval_longmemeval.py     --n 500 --systems recent_window,naive_rag,mem0,ours

# 3. figures
python scripts/make_figures.py
```

If a full run is slow, drop `--n` to 60 — the loaders subsample
stratified by category so the five-axis decomposition stays valid
(document the subsampling in the report, per the plan's risk table).

---

## 7. Notes & caveats

- **Offline scoring is a lower bound.** It checks whether the gold fact
  reached the prompt, not generation quality. On free-form LongMemEval
  answers it under-reports `ours` (whose edge is ROI/selectivity under
  the real judge, not raw substring recall). Use real mode for headline
  numbers; offline for reproducible structure/sanity.
- **Caching.** Delete rows from the `llm_cache` table (or the SQLite DB)
  only if you intend to re-spend tokens; otherwise leave it for free
  re-runs. Bump the prompt version in `prompts/memory_judge.py` to
  invalidate stale judgements.
- **mem0 baseline** needs `pip install -e ".[memory]"` (pinned
  `mem0ai==0.1.40`); without it, drivers print a clear skip message and
  continue with the other systems.
- **Reproducibility.** Probe/persona generators are seeded; offline runs
  are fully deterministic. `python -m pytest tests/ -q` (113 tests)
  validates the whole stack before any token spend.
