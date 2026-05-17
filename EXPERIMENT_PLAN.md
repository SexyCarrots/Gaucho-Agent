# Selective Memory for Gaucho-Agent — Implementation & Experiment Plan

> **2-week solo build, laptop-only, ~10M GPT-4o-mini tokens/day budget.**
> Week 1 builds the system. Week 2 evaluates it through five experiments designed to go beyond standard accuracy reporting.
> The novelty of this project is not the system — `mem0`/Letta exist. **The novelty is the evaluation methodology.**

---

## 1. TL;DR — the bet

Most LLM-agent memory papers report a single number: "X% accuracy on benchmark Y." That number conflates four very different questions:

1. Did the system **store** the right things?
2. Did it **retrieve** the right things at query time?
3. Did it use the retrieved memories to **generate** a sensible answer?
4. Was the **cost** worth the accuracy gain?

The contribution of this project is a **multi-axis evaluation framework** that answers all four questions separately, applied to a selective-memory architecture built on top of `mem0` + Gaucho-Agent. The system itself is unambitious; the evaluation is the research.

---

## 2. The two-week shape

| Week | Focus | Outcome at end of week |
|---|---|---|
| **Week 1 (Days 1–7)** | Build the memory layer | `gaucho chat` remembers across sessions; `mem0` plugged in as baseline; LongMemEval-S harness runs end-to-end |
| **Week 2 (Days 8–14)** | Five evaluation experiments + writeup | Five tables/figures, each answering a distinct research question; final report draft |

Each day ends with a *runnable artifact*. If a day slips, the previous day's artifact is still demoable.

---

## 3. Constraints & token budget

- **Laptop only** — no GPU, no large local models.
- **Token budget:** ~10M gpt-4o-mini tokens/day via OpenAI data-sharing tier (more than enough). Reserve ~1M gpt-4o tokens for the final LLM-as-judge scoring pass.
- **Total experiment budget:** plan to use ~12M tokens across all five experiments (with caching, ~8M actual calls).
- **Don't break existing.** All 41 tests still pass after each commit. New code lives behind `USE_MEMORY=1`.

### Budget allocation per experiment

| Experiment | Calls model | Token estimate | What it consumes |
|---|---|---|---|
| Build & smoke test | gpt-4o-mini | ~500K | judge calls during dev |
| Synthetic probe generation | gpt-4o-mini | ~300K | 50 multi-session probes |
| EXP-1 Counterfactual main run | gpt-4o-mini | ~3.5M | 100 Q × (4 systems + 1 no-memory) |
| EXP-2 Budget Pareto sweep | gpt-4o-mini | ~2M | 50 Q × ours at K∈{8,32,128,∞} |
| EXP-3 Adversarial stress test | gpt-4o-mini | ~2.5M | 90 adversarial conversations × 2 systems |
| EXP-4 Process forensics | gpt-4o-mini | ~500K (mostly reuses EXP-1 logs) | re-scoring stored logs |
| EXP-5 Provenance | gpt-4o (judge) | ~600K | 200 explanation traces judged |
| Ablations | gpt-4o-mini | ~1.5M | 50 Q × 3 ablation variants |
| Final accuracy judging | gpt-4o | ~400K | one pass over all answers |
| **Total** | | **~11.8M** | |

---

## 4. Architecture (file additions to `gaucho_agent/`)

All paths match the actual repo layout (`gaucho_agent/{models,services,prompts,tools}/`, `scripts/`, `tests/`).

```
gaucho_agent/
  models/memory.py              # MemoryItem SQLModel
  services/memory.py            # MemoryService: store · retrieve · resolve_conflicts
  services/memory_judge.py      # LLM-as-judge wrapper (returns structured JSON)
  services/memory_backend.py    # uniform interface: ours | mem0 | naive_rag | recent_window
  prompts/memory_judge.py       # few-shot prompt template (Python literal)
  prompts/user_simulator.py     # personas for adversarial users (EXP-3)
  tools/memory_recall.py        # exposes recall as a tool the chat loop can call
scripts/
  eval_longmemeval.py           # primary benchmark driver
  eval_memoryagentbench.py      # TTL + CR subsets only
  eval_counterfactual.py        # EXP-1
  eval_budget_sweep.py          # EXP-2
  eval_adversarial.py           # EXP-3
  eval_provenance.py            # EXP-5
  build_synthetic_probes.py     # generates 50 Gaucho probes via gpt-4o-mini
  simulate_user.py              # LLM-driven user for EXP-3
tests/
  test_memory_judge.py
  test_memory_service.py
  test_memory_integration.py
data/
  longmemeval_s/                # gitignored
  synthetic_probes.json         # checked in (~150KB)
  adversarial_conversations.json
results/
  exp1_counterfactual.csv
  exp2_budget_sweep.csv
  exp3_adversarial.csv
  exp4_process_metrics.csv
  exp5_provenance.csv
  ablations.csv
figures/
  *.pdf
```

### 4.1 `MemoryItem` schema

```python
# gaucho_agent/models/memory.py
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional, Literal

MemoryType = Literal["preference", "profile", "schedule", "plan"]

class MemoryItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    session_id: str = Field(index=True)
    content: str                       # canonical fact ("user is vegetarian")
    raw_turn: str                      # original utterance (for traceability)
    mem_type: MemoryType
    subject_key: str                   # for override matching: "diet", "lab_schedule"
    created_at: datetime
    embedding: bytes                   # numpy float32 as bytes
    superseded_by: Optional[int] = None
    # Provenance fields for EXP-5
    source_turn_idx: int
    judge_confidence: float            # 0..1 from the LLM-judge
```

### 4.2 LLM-as-judge JSON contract

```json
{
  "store": true,
  "type": "preference",
  "salient_fact": "user is vegetarian",
  "subject_key": "diet",
  "confidence": 0.92,
  "supersedes": "any prior 'diet' memory for this user"
}
```

### 4.3 Retrieval scoring

```python
score(q, m) = α * cosine(emb(q), emb(m.content))         # semantic match
            + β * I[infer_query_type(q) == m.mem_type]   # type match
            + γ * exp(-Δt / τ)                            # recency decay
```

Defaults `α=0.7, β=0.2, γ=0.1, τ=14 days`. Skip items with `superseded_by IS NOT NULL`. Tunable in EXP-2.

---

## 5. Week 1 — Build (Days 1–7)

| Day | Task | Done when |
|---|---|---|
| 1 | `MemoryItem` + migration. `MemoryService.store/retrieve` with heuristic policy. MiniLM embedding integration. | `pytest tests/test_memory_service.py` passes; embeddings cached in SQLite |
| 2 | Wire into chat loop behind `USE_MEMORY=1`. Smoke test: tell-in-session-1, recall-in-session-2. | manual: `gaucho chat` remembers a fact across sessions using heuristic |
| 3 | `services/memory_judge.py` + `prompts/memory_judge.py`. Structured JSON output with caching by turn hash. | 10 known-positive and 10 known-negative cases pass in unit tests |
| 4 | Plug judge into `MemoryService.store`. Add type-aware retrieval scoring. Recency-aware override resolver. | retrieval test: "I'm vegetarian" then "I eat chicken now" → only newer returned |
| 5 | `MemoryBackend` interface; integrate `mem0ai` as parallel implementation. `MEMORY_BACKEND` env var. | both backends work via `gaucho chat`; `pytest tests/test_memory_integration.py` passes |
| 6 | Download LongMemEval-S. `scripts/eval_longmemeval.py` runs all 4 systems on a 10-Q smoke subset. | first numbers committed to `results/smoke.csv` |
| 7 | `scripts/build_synthetic_probes.py` — generate 50 Gaucho probes via gpt-4o-mini. Hand-review & checkpoint. | `data/synthetic_probes.json` exists with ground-truth memories annotated |

---

## 6. Evaluation philosophy — the centerpiece

Standard practice is: feed history, ask question, score answer with an LLM-judge, report accuracy. This collapses three independent failure modes (storage, retrieval, generation) into one number and ignores cost entirely.

This project instead operationalizes **five distinct evaluation questions**, each with its own experiment, metric, and expected pattern of results:

| # | Research question | Experiment | Headline metric |
|---|---|---|---|
| 1 | *How much accuracy is memory actually contributing — and at what cost?* | EXP-1: Counterfactual | ΔAccuracy and Memory ROI |
| 2 | *Is the system smart about ranking memories, or does it just keep everything?* | EXP-2: Budget Pareto | Selectivity premium |
| 3 | *Does the agent's mental model survive realistic user noise (contradictions, distractors, paraphrase)?* | EXP-3: Adversarial | Robustness gap |
| 4 | *Which stage (store / retrieve / override) actually fails when accuracy is bad?* | EXP-4: Process forensics | Store-F1, Retrieve-F1, Override-precision |
| 5 | *When the agent gets it right, was it for the right reasons?* | EXP-5: Provenance | Provenance accuracy |

Together these five let me make claims of the form *"system X wins on dimension Y because Z"* instead of *"system X is 3 points better."* That shape is rare in the memory-agent literature and is the publishable contribution.

---

## 7. Week 2 — Experiments (Days 8–14)

### 7.1 EXP-1 — Counterfactual ΔAccuracy + Memory ROI (Day 8)

**Hypothesis.** Memory contributes nonzero accuracy only on memory-dependent questions; the *delta* and the *cost-per-delta* differ sharply across systems.

**Protocol.**
- Pick 100 questions from LongMemEval-S, balanced across the 5 categories.
- Run each system in two modes: `with_memory` and `no_memory` (memory layer disabled; only recent-window context).
- For each system, compute per-category ΔAccuracy and total Memory ROI.

```bash
python scripts/eval_counterfactual.py --n 100 --systems recent,naive_rag,mem0,ours
```

**Metrics.**
```
ΔAccuracy_c    = Acc(system, with_memory, category c) − Acc(system, no_memory, category c)
ΔTokens         = mean tokens added to prompt by memory layer per query
Memory ROI      = ΔAccuracy / ΔTokens (accuracy points per 1K tokens)
```

**Expected pattern.** Recent-window has ΔAccuracy = 0 by construction (no memory). Naive RAG has positive ΔAccuracy but high ΔTokens → low ROI. `mem0` has moderate Δ and moderate ROI. **Ours should have positive ΔAccuracy comparable to mem0 at substantially lower ΔTokens, yielding the highest ROI.**

**Why novel.** Most papers report only `Acc(with_memory)`. Reporting the **counterfactual delta** isolates memory's actual contribution from the generator's baseline competence. Memory ROI then makes cost a first-class metric, which is essentially absent from current memory-agent benchmarks.

---

### 7.2 EXP-2 — Memory budget Pareto + Selectivity premium (Day 9)

**Hypothesis.** Selective storage isn't just about *what* you store — it's also about *how well you rank* what you've stored. Under a tight memory budget, a better-ranked store dominates.

**Protocol.**
- Same 50 questions as EXP-1 subset.
- For `ours` and `mem0`, evaluate at memory-budget caps K ∈ {8, 32, 128, ∞} memory items retrievable at query time. (Cap is applied *after* the store is fully built, so this measures retrieval ranking quality, not storage.)
- Compute accuracy at each K.

```bash
python scripts/eval_budget_sweep.py --n 50 --K 8,32,128,inf --systems mem0,ours
```

**Metrics.**
```
Selectivity premium = Acc(K=32) / Acc(K=∞)   ∈ [0,1]
Pareto curve = {(K, Acc(K)) : K ∈ sweep}
```

**Expected pattern.** At K=∞ all systems plateau. As K shrinks, naive RAG collapses (no quality ranking), `mem0` degrades moderately, **ours retains the largest fraction of its full-budget accuracy** thanks to type-aware retrieval. Selectivity premium > 0.85 for ours, < 0.6 for mem0.

**Why novel.** The literature treats "memory ranking quality" as implicit — measured only through downstream accuracy at unconstrained K. The Pareto sweep makes ranking quality directly visible, and the selectivity premium is a single-number summary of how well a system prioritizes what it has stored.

---

### 7.3 EXP-3 — Adversarial stress test with LLM-simulated users (Day 10)

**Hypothesis.** Real users are messy. They contradict themselves, drop irrelevant facts, paraphrase, and forget. A memory system that wins on clean benchmarks may collapse under realistic noise — and `ours` should collapse less.

**Protocol.** Use gpt-4o-mini to drive three adversarial user personas across multi-session conversations:

```python
# gaucho_agent/prompts/user_simulator.py
PERSONAS = {
    "contradictory": "You frequently change your mind. Mention a preference, then explicitly contradict it 1-2 sessions later. Vary how you signal the change ('actually...', 'I lied earlier...', 'now I prefer...').",
    "distractor": "You bury one important fact ('I have a peanut allergy') among 10 throwaway personal details ('I like the color blue', 'my dorm faces east'). Test whether the agent extracts signal from noise.",
    "paraphraser": "When asking memory-dependent questions later, never use the same wording you used when introducing the fact. Synonyms, indirect references, different grammatical framings.",
}
```

- 30 conversations × 3 personas × 2 systems (ours, mem0) = 180 conversation runs.
- Each conversation: 4 sessions of ~12 turns, 1 final memory-dependent question, ground-truth answer pre-defined when generating the persona script.

```bash
python scripts/simulate_user.py --personas all --n 30 --out data/adversarial_conversations.json
python scripts/eval_adversarial.py --systems ours,mem0 --in data/adversarial_conversations.json
```

**Metrics.**
```
Robustness gap = Acc(persona) − Acc(clean baseline same questions)
Per-persona accuracy
Storage rate inflation under "distractor" (memories stored / turn — does the system over-store?)
```

**Expected pattern.** All systems degrade under all three personas. `ours` should degrade least on **contradictory** (recency-aware override kicks in) and **distractor** (LLM-judge filters noise). Paraphraser is the hardest — pure retrieval problem; expect modest separation.

**Why novel.** Adversarial / robustness testing for memory systems is in its infancy. Existing benchmarks use clean, scripted conversations. LLM-simulated users with explicit failure-mode personas let us stress-test in a reproducible, controllable way that no static dataset can.

---

### 7.4 EXP-4 — Process-level forensics: store/retrieve/override F1 (Day 11)

**Hypothesis.** Terminal accuracy is the product of three latent factors: did you store the right thing? did you retrieve it? did you use it correctly? Decomposing these tells us *where* to improve, not just *whether* to.

**Protocol.** Reuses the logs from EXP-1 — no new model calls needed except for the LLM-judge scoring pass. For each question:
1. **Ground truth.** LongMemEval annotates the "needle" turn (or turns) — what *should* have been stored. For our synthetic Gaucho probes, we annotate these by construction.
2. **Store-F1.** Compare actual stored memories against the gold "should-store" set. Precision = relevant-stored / total-stored. Recall = relevant-stored / total-relevant.
3. **Retrieve-F1.** At query time, top-K retrieved vs. gold "needed for this answer."
4. **Override-precision.** For questions in the "knowledge update" category, was the override applied correctly?

```bash
python scripts/eval_process_metrics.py --logs results/exp1_counterfactual.csv
```

**Metrics.**
```
Store-F1, Store-precision, Store-recall
Retrieve-F1, Retrieve@K
Override-precision = correct_overrides / total_overrides_fired
Storage rate = stored_memories / total_turns  (calibration sanity check)
```

**Expected pattern.** Naive RAG has store-recall ≈ 1 (stores everything) but store-precision ≈ 0.1 (mostly noise). `mem0` has moderate F1. **Ours should have the highest Store-F1 and the highest Override-precision** — and the gap should be largest on the knowledge-updates category.

**Why novel.** This is the single most under-explored evaluation methodology in the memory-agent space. Almost no paper reports store-F1 or override-precision; the field treats memory as a black box scored only by terminal accuracy. Process metrics let us diagnose exactly which stage of a memory pipeline is broken.

---

### 7.5 EXP-5 — Memory provenance: did it answer for the right reasons? (Day 11)

**Hypothesis.** An agent can produce a correct answer for entirely wrong reasons — coincidence, prior knowledge, or hallucination that happens to match. A *trustworthy* memory agent uses the *correct memories* to produce correct answers.

**Protocol.**
- For 100 questions from EXP-1, log the full retrieval set (the memories that were in the prompt at generation time).
- Use **gpt-4o** as a provenance judge with this rubric:

```
Given (question, retrieved memories, agent's answer):
  - Correct answer?                                     [yes/no]
  - Did the answer DEPEND on a memory in the retrieved set?   [yes/no]
  - If yes, which memory? Was it the gold-relevant memory?    [memory_id or "wrong memory used"]
```

**Metrics.**
```
Provenance accuracy = P(used gold memory | answer was correct)
"Lucky guesses" = P(correct ∧ ¬used relevant memory) / P(correct)
"Distracted right" = P(correct ∧ used wrong memory) / P(correct)
```

**Expected pattern.** Recent-window has high "lucky guess" rate (no memory to use, so correct answers are either prior knowledge or coincidence). Naive RAG has moderate distracted-right rate (correct memory was in the bag, but so was junk). **Ours should have the highest provenance accuracy** — correct answers traced to correct memories.

**Why novel.** Interpretability of memory use is essentially absent from the benchmark literature. Provenance accuracy converts a vague "is this trustworthy?" question into a concrete measurable, and it's especially relevant for agents in any high-stakes setting (medical, legal, academic advising).

---

### 7.6 Days 12–14 — Ablations, writeup, polish

| Day | Task | Done when |
|---|---|---|
| 12 | Three ablations on the EXP-1 setup: `−typing` (β=0), `−recency` (γ=0), `−judge` (heuristic only). Quantify what each contributes. | `results/ablations.csv` |
| 13 | Generate all figures (Pareto curve, per-category ΔAccuracy bars, robustness gap, F1 breakdowns, provenance scatter). Draft final report. | `figures/` complete; report draft submitted |
| 14 | Final presentation slides update + dry run; polish; buffer day. | demo runs in <90s; deck final |

---

## 8. Headline figures to produce (one per experiment)

1. **EXP-1:** Grouped bar chart, x-axis = LongMemEval category, y-axis = ΔAccuracy. One bar per system. Companion table: Memory ROI.
2. **EXP-2:** Pareto curve, x-axis = memory budget K (log scale), y-axis = accuracy. One line per system. Vertical line at K=32 marks the budget at which selectivity premium is reported.
3. **EXP-3:** Heatmap, rows = personas, columns = systems, cell = accuracy. Annotate each cell with robustness gap.
4. **EXP-4:** Stacked horizontal bar chart per system showing Store-F1, Retrieve-F1, Override-precision. Lets reviewers see *which stage* is each system's weak link.
5. **EXP-5:** Stacked bar — for each system, decompose correct answers into (used gold memory) / (used wrong memory) / (didn't use any memory). Provenance accuracy is the gold-memory slice.

A reader who only looks at these five figures should understand the entire contribution.

---

## 9. Risk mitigations

| Risk | Mitigation |
|---|---|
| Token budget overrun mid-week 2 | Cache every gpt-4o-mini call by `hash(prompt) → response` in SQLite. Re-runs are free. Set hard daily caps on the harness. |
| LLM-as-judge calls during storage are too slow on laptop | Batch judge calls (10 turns per request via prompt concatenation); cache aggressively; pre-compute on the conversation upfront, not at chat time. |
| LongMemEval-S still too slow at 100Q | Drop to 60Q stratified subset across 5 categories. Document the subsampling in the report. |
| `mem0ai` integration breaks (API changes) | Pin `mem0ai==X.Y.Z` in pyproject.toml. Wrap behind `MemoryBackend` interface so swapping it out is local. |
| Adversarial conversations are unrealistic | Hand-review 10 generated conversations on Day 10 morning; if persona drift, refine prompts before running the full 180. |
| Selective layer underperforms `mem0` | Still report honestly + decompose with EXP-4. Process metrics will tell us which stage failed and that itself is a finding. The whole point of the framework is making *negative* results diagnostic. |
| GPT-4o data sharing tier paused | Fall back to gpt-4o-mini for the final judging pass too. Validate the 4o-mini judge against 4o on 50 samples first. |

---

## 10. References (read these before Week 1 starts)

**LongMemEval** — Wu et al., ICLR 2025. arXiv:2410.10813. <br>
The primary benchmark. Five-axis decomposition; needle-in-history evaluation; LLM-judge protocol at 97% human agreement. We use the `-S` subset and adopt their judge protocol.

**MemoryAgentBench** — Hu, Wang & McAuley, ICLR 2026. arXiv:2507.05257. <br>
The secondary benchmark. Incremental-turn protocol; four axes including Conflict Resolution and Test-Time Learning that map directly onto our contributions. We use the TTL and CR subsets.

---

## 11. Definition of done (project-level)

- [ ] `USE_MEMORY=1 gaucho chat` remembers personal facts across sessions, with the LLM-as-judge deciding what to store
- [ ] Four systems (recent-window, naive RAG, mem0, ours) plug into the same `MemoryBackend` interface
- [ ] All five experiments completed with results CSVs and figures
- [ ] Three ablations completed
- [ ] Synthetic Gaucho probe set (50 Q) generated and annotated with gold-memory references
- [ ] Final report submitted with the five headline figures as the results section
- [ ] Final 6-min presentation rehearsed; deck final
- [ ] All 41 existing tests still pass; ≥10 new tests for memory components
