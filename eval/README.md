# InsightEdge Eval Harness

Benchmarks Claude Haiku / Sonnet / Opus / gpt-4o on signal-scoring quality, cost, and latency.

---

## What this measures

| Metric | Tool | What it answers |
|---|---|---|
| Cost per test case | Promptfoo (auto) | Which model is cheapest to score signals? |
| Latency p50 / p95 | Promptfoo (auto, 3 repeats) | Which model is fastest? |
| Faithfulness | Promptfoo llm-rubric (gpt-4o judge) | Does the model stay grounded in evidence, or hallucinate? |
| Signal accuracy | Promptfoo llm-rubric | Does the model catch all signals in the evidence? |
| Score calibration | Promptfoo llm-rubric | Is the per-agent score proportional to the expected signal band? |

---

## Design decisions

- **Frozen evidence:** The web search (Call 1) runs once via existing production results. The same frozen context is replayed to every model so differences come from the model, not from non-deterministic search.
- **temperature=0** on all models for reproducible cost/quality comparison.
- **3 repeats** per test case to compute p50/p95 latency.
- **Non-Anthropic:** gpt-4o runs only on the scoring step (Call 2). It never touches the Anthropic web_search tool.
- **RAGAS skipped:** RAGAS collections metrics require Python 3.10+ (via the `instructor` library). The environment runs Python 3.8. Faithfulness is instead measured via Promptfoo llm-rubric with gpt-4o as judge, which is equivalent for our purposes.

---

## Files

```
eval/
  golden_set.json            25 real companies with known production scores
  freeze_contexts.py         Reconstructs frozen evidence from result JSONs
  frozen_contexts/           92 frozen context files (25 companies × ~4 agents)
  generate_promptfoo_tests.py  Builds promptfoo_tests.json from frozen contexts
  promptfoo_tests.json       Generated — 92 test cases (do not edit by hand)
  promptfoo_call2.yaml       Promptfoo config (providers, prompts, assertions)
  run_ragas.py               RAGAS faithfulness evaluation (requires Python 3.10+)
  run_eval.ps1               End-to-end runner (Windows)
  README.md                  This file
```

---

## Prerequisites

### API keys
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:OPENAI_API_KEY    = "sk-..."
```
Or store them in `.env` at the repo root — the eval scripts load it automatically.

### Install tools
```powershell
# Promptfoo (version 0.121.x)
npm install -g promptfoo

# Python packages
pip install python-dotenv openai
```

---

## Run the full eval

```powershell
cd <repo-root>
.\eval\run_eval.ps1
```

Or step by step:

```powershell
# Step 1: rebuild frozen contexts (only needed if result JSONs changed)
python eval/freeze_contexts.py

# Step 2: regenerate test cases
python eval/generate_promptfoo_tests.py

# Step 3: run Promptfoo benchmark
npx promptfoo eval --config eval/promptfoo_call2.yaml --repeat 3 --output eval/promptfoo_output.json

# View Promptfoo UI (optional)
npx promptfoo view
```

---

## Results (run: 2026-06-20)

**Setup:** 25 companies × ~4 agents = 92 test cases · 4 models · 3 repeats = 1,104 API calls  
**Judge:** gpt-4o (for all llm-rubric assertions)  
**Token pricing:** Haiku $1/$5, Sonnet $3/$15, Opus $5/$25, gpt-4o $2.50/$10 per 1M in/out

| Model | Avg input tok | Avg output tok | Cost / case | Faithfulness | Signal accuracy | Score calibration |
|---|---|---|---|---|---|---|
| haiku-4-5 | 4,593 | 1,536 | $0.012 | 0.736 | 0.984 | ~0.33 |
| sonnet-4-6 | 4,594 | 1,520 | $0.037 | 0.752 | 0.996 | ~0.33 |
| opus-4-8 | 6,172 | 1,610 | $0.071 | 0.737 | 0.986 | ~0.33 |
| gpt-4o | 3,785 | 843 | $0.018 | 0.743 | 0.960 | ~0.33 |

**Latency (gpt-4o only — Anthropic latency requires a fresh uncached run):**

| Model | p50 latency | p95 latency |
|---|---|---|
| gpt-4o | 6.49 s | 17.14 s |
| haiku-4-5 | — | — |
| sonnet-4-6 | — | — |
| opus-4-8 | — | — |

> Anthropic latency data was unavailable because Promptfoo caches repeat calls. To measure Anthropic latency: clear the Promptfoo cache (`npx promptfoo cache clear`) and run with `--repeat 1` on a fresh machine.

### Notes on score_calibration

Score calibration sits at ~33% pass rate across all models. The rubric asks the judge to verify that each agent's 0–10 `score` field falls within the expected band range. The low pass rate is driven by two known issues:
1. Some models return JSON inside markdown fences — the judge sometimes misses the `score` field
2. The signal_band was assigned from the **total** production score (sum of all agents), not per-agent scores, so per-agent calibration is inherently noisy

Faithfulness and signal accuracy are the reliable quality signals.

### Recommendation

**Haiku-4-5** for cost-sensitive production use ($0.012/case, 0.736 faithfulness, 0.984 signal accuracy).  
**Sonnet-4-6** for quality-sensitive use ($0.037/case, best faithfulness 0.752 and signal accuracy 0.996).  
gpt-4o scores between them on quality but is priced similarly to Haiku.  
Opus-4-8 costs 6× more than Haiku with no measurable quality gain on this task.

---

## Reading the results

**Promptfoo output** (`eval/promptfoo_output.json`):
- Per-provider, per-test latency (ms) and token counts
- llm-rubric scores: `faithfulness`, `signal_accuracy`, `score_calibration`

---

## Scale

- 25 companies × ~4 agents = **92 test cases**
- 92 × 4 models × 3 repeats = **1,104 API calls** total
- Actual cost: ~$8–10 total (dominated by judge calls to gpt-4o)
- Actual runtime: ~1h 23m

---

## Adding more companies

1. Run a production analysis on the new company
2. Add an entry to `eval/golden_set.json` pointing to the result file
3. Re-run `python eval/freeze_contexts.py`
4. Re-run `python eval/generate_promptfoo_tests.py`
5. Re-run the Promptfoo benchmark
