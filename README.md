# Sonar AI Sales Agent

A multi-role AI-powered sales intelligence platform that researches target accounts and surfaces buying signals to help sales teams prioritise outreach.

## Overview

Two workstreams, each with their own signal pipeline:

| Workstream | Target | Key Signals |
|---|---|---|
| **Enterprise (Territory Manager)** | 100–500 regulated-industry accounts | Tech stack, hiring, news, regulatory impact, stakeholder intelligence, company position |
| **Velocity (Mid-market)** | SMB / mid-market accounts | Tech stack, hiring, news, developer pain points |

Both workstreams produce a ranked propensity-to-buy report and a customised outreach email draft.

## Features

- Upload a CSV/XLSX account list or auto-discover companies by country and industry
- Per-account signal research across 8 specialised agents running in sequence
- Propensity-to-buy scoring and ranking
- Company position classification (AI Leader → Laggard)
- Stakeholder intelligence with personality inference (ENT only)
- Outreach Suggest: recommends the strongest email hook based on all gathered signals
- Email draft generator personalised to contact role and personality
- Token usage tracking with cost projections
- **Crash-safe runs:** results are checkpointed to disk after every account, so an interrupted batch can be resumed without re-running completed work
- **Automatic retry on rate limits:** all Anthropic API calls retry transient `429` / `5xx` / connection errors with exponential backoff and `Retry-After` honouring

## Agents

| Agent | Role |
|---|---|
| Tech Stack | Detects CI/CD tools, cloud presence, GitHub activity |
| Hiring Patterns | Scans job postings for DevSecOps / engineering growth signals |
| Public News | Finds recent tech-related news and product announcements |
| Regulatory Impact | Maps upcoming regulations to the account's industry (ENT only) |
| Company Profile | Summarises what the company does, their business model, AI posture |
| Stakeholder Intelligence | Finds technical leadership and infers personality colour (ENT only) |
| Developer Pain Points | Searches Stack Overflow, Reddit, GitHub for dev pain signals (Velocity only) |
| Company Position | Classifies account as AI Leader / Early Adopter / Mainstream / Skeptic / Laggard |
| Outreach Suggest | Synthesises all signals and recommends the strongest outreach hook |

## Setup

### Prerequisites

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)

### Install

```bash
git clone https://github.com/xavieryeong/InsightEdge.git
cd InsightEdge
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Run

```bash
streamlit run main.py
```

## Deployment

The app is deployed on Streamlit Community Cloud. Pre-run demo batches are included in the repo so customers can browse results without running the pipeline.

To add new batches to the deployed app after running locally:

```bash
git add data/
git commit -m "add new batch"
git push
```

## Project Structure

```
agents/          # One folder per agent — prompt, config, agent logic
config/          # API key settings
data/            # Saved research results (JSON)
ui/              # Streamlit pages and rendering helpers
main.py          # App entry point and navigation
```

## Reliability

### Resume from interruption

While a batch is running, the director writes a `<timestamp>_<source>_INPROGRESS.json` checkpoint
into `data/results/{ent,velocity}/` after every account. If the process is killed or the browser
tab is closed mid-run, re-submitting the same source list automatically resumes:

```
Resuming previous run — 47 account(s) already analysed will be skipped.
```

Resume is keyed on `(company, domain)`. The partial file is replaced atomically (temp-write +
rename) so it is always a valid JSON document. On successful completion the file is renamed to
its final `<timestamp>_<source>.json`. Partial files are not shown in the run list.

### Retry on transient API errors

`agents/base.py:safe_create` wraps every `client.messages.create` call. Retries:

- `RateLimitError` (HTTP 429)
- `APIStatusError` with status 5xx
- `APIConnectionError`

Backoff is exponential (base 2s, ±30% jitter, capped at 60s), up to 6 attempts. If the response
includes a `retry-after` header, it is honoured in place of the computed backoff. 4xx errors
other than 429 are not retried — they fail fast.

## Scaling notes

The pipeline is currently single-threaded across accounts. With ~860 K input tokens per ENT
account on Anthropic Tier 1 (~40 K input TPM, ~50 RPM), the practical ceiling for a single
uninterrupted batch is roughly 10–20 accounts in 20–40 minutes. Larger batches are reliable —
they will checkpoint and resume — but will take multiple hours.

Higher throughput (account-level concurrency, process-wide rate limiter, background-thread UI)
is planned in subsequent phases.

## Security

- API keys are loaded from `.env` (local) or Streamlit Secrets (cloud) — never hardcoded
- `data/` contains AI-generated intelligence about public companies only
- `.env` is excluded from version control
