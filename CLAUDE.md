# Sonar AI Sales Agent — MVP

## Working Agreement

> **Always brief the user before building anything.** Present the plan, get confirmation, then proceed. Never start coding or creating files without explicit approval first.

## Project Overview

**Full name:** Multi Role AI Digital Sales Agent  
**Short name:** Sonar AI Signal / Sales Agent  
**Status:** MVP — build step by step, validate before proceeding to next phase  
**Stakeholders:** Sponsor, Project Owner, Sales Lead, Technical Lead

## Problem Statement

Sonar's sales teams face:
- Inefficient ability to schedule meetings
- Unable to spark conversations with the right target audience
- Lack of quality leads
- Insufficient lead volume

## Vision

A single desktop application serving two GTM segments:
- **Velocity / mid-market reps** — outreach to immediate opportunities based on propensity-to-buy signals
- **Territory Managers (ENT)** — feed a target account list and identify key buying signals across defined indicators

Three business pillars: **Listen → Market → Outbound**

---

## User Roles & Modes

### Role A: Territory Manager (Enterprise)
- **Input:** Feed an account list of 100–500 regulated-industry accounts
- **Agent behavior:** Ingests list → chooses ENT indicators → runs analysis → ranks by propensity to buy
- **Output:**
  - Report with data across all analyzed signal categories, ranked by propensity to buy
  - Customized email targeting a specific personality (e.g. Head of AI, CTO) based on social/inference signals
  - Customized product marketing message to keep Sonar top-of-mind

### Role B: Velocity (Mid-market / SMB)
- **Input (two options):**
  - Option A: "Create a list" — agent curates mid-market accounts from SFDC or web, programmed with ICP criteria (excludes ENT list)
  - Option B: Feed a Velocity list manually
- **Agent behavior:** Ingests input → chooses Velocity indicators (ENT-specific indicators excluded) → runs analysis
- **Output:**
  - Report ranked by propensity to buy
  - Customized email based on developer pain points / social listening signals (Stack Overflow, Reddit, GitHub, Sonar community)

---

## Signal Indicators

| Indicator | Velocity (V) | Enterprise (ENT) | Data Sources |
|---|---|---|---|
| Hiring patterns | ✅ | ✅ | LinkedIn, target account careers page |
| Public news (tech-related) | ✅ | ✅ | Web scraping, news APIs |
| Technology stack analyzer | ✅ | ✅ | GitHub, ZoomInfo, CI/CD tools, Cloud presence |
| Regulatory impact analysis | ❌ | ✅ | Regulatory news, industry publications |
| Pain points / Social listening | ✅ | ❌ | Stack Overflow, Reddit, GitHub, Sonar community |
| Company position (leader / skeptic / laggard) | ❌ | ✅ | Web inference |
| Personality inference (4-colour model) | ❌ | ✅ | LinkedIn, speeches, events, articles |
| Contact role mapping (power map) | ❌ | ✅ | LinkedIn |

### Notes on Indicators
- **Tech stack, hiring, public news** are deterministic / black-and-white — high confidence
- **Personality inference** is subjective — agent infers from online data (speech style, event attendance, article tone). Flag as probabilistic, not definitive. Sales team must understand this caveat.
- **Scoring model** is prompt-driven. Team can adjust weights per indicator in the prompt without code changes. Different regions / salespeople may weight differently.

---

## Architecture: Multi-Agent Sequential System

```
User Input
    │
    ▼
[Director / Coordinator Agent]
    │
    ├──► [Hiring Signal Agent]
    ├──► [Tech Stack Agent]
    ├──► [Public News Agent]
    ├──► [Regulatory Impact Agent]     ← ENT only
    ├──► [Social Listening Agent]      ← Velocity only
    ├──► [Company Position Agent]      ← ENT only
    ├──► [Personality Inference Agent] ← ENT only
    │
    ▼
[Scoring & Ranking Agent]
    │
    ▼
[Email / EDM Drafting Agent]
    │
    ▼
Output (Report + Emails)
```

**Architecture principles:**
- **Sequential, not orchestrator** — no branching or parallel orchestration needed
- **Independent agents** — each signal agent is a separate, self-contained module (easier to maintain, fine-tune, swap)
- Each agent has its own memory / skill prompt
- Director agent coordinates the pipeline and aggregates results
- Human-in-the-loop for email sending (agent drafts, human reviews and sends)

---

### Data Sources & APIs
- LinkedIn (scraping or API)
- GitHub (API)
- ZoomInfo (API)
- Stack Overflow (API / scraping)
- Reddit (API)
- Sonar community (scraping)
- SFDC / Salesforce (CRM data for Velocity list)
- General web / news scraping

### Agent Memory System
- Agents must retain context of what they are supposed to do on every invocation
- Skills written in structured 3-part format (to be defined)
- Memory refreshes on each skill call so agent "remembers" its role and instructions

### Skills / Prompt Structure
- Skills written in a 3-part structured format (research required)
- Framework to be documented so the team can write and maintain skills independently

---

## Output Specifications

1. **Propensity-to-Buy Report** — ranked list of accounts with signal data per category
2. **Customized Outreach Email** — tailored to target personality (ENT) or developer pain point (Velocity)
3. **Product Marketing Message** — thought leadership / content recommendation to keep Sonar top-of-mind

Email style: short, direct, personalized — goal is to get a reply / spark a conversation, not a generic blast.

---

## Non-Functional Requirements

- **Maintainability:** The solution architect team must be able to fine-tune prompts and scoring without vendor help
- **Training:** 2-day training planned for solution architects / technical sales profiles post-build
- **Fine-tuning vs fixing:** Team trained to fine-tune (adjust prompts, add indicators, change scoring weights); vendor not expected to provide ongoing Day 2 support
- **Clean engagement model:** MVP is self-contained; integration into Sonar environment is a separate paid engagement if approved

---

## Engineering Conventions

These are load-bearing implementation details that future work must respect. The architecture is single-threaded today but every contract below is written to be thread-safe so account-level concurrency can be added later without touching agent internals.

### Agent contract

Every `BaseAgent` subclass exposes one entry point (`run(...)` for signal agents, `analyse(...)` for the advisor, `draft(...)` for the email agent) that:

1. Returns a `dict` for the account's signal output.
2. Includes a reserved key `_usage: {"input": int, "output": int}` aggregating all Claude API tokens spent inside that call. The director pops this key into `account_result["token_usage"][agent_key]`; downstream code never sees `_usage` on the signal dict.
3. Holds **no mutable token state on `self`**. `BaseAgent` no longer has `_input_tokens` / `_output_tokens` / `_reset_usage` / `_get_usage`. Adding any back will silently break concurrency.

When adding a new helper that calls the Anthropic SDK directly, return its usage alongside its result (`(text, limitations, usage)` is the established shape — see `agents/tech_stack/claude_tech_search.py` for the canonical form). Don't accumulate to `self`.

`BaseAgent.ask_claude(system, user) -> (text, usage_dict)` — callers must unpack. The `usage_dict` keys are `"input"` and `"output"`.

### Calling the Anthropic SDK

**All** `client.messages.create` calls must go through `agents.base.safe_create(client, **kwargs)`. It applies retry with exponential backoff + jitter (base 2s, ±30%, capped at 60s, max 6 attempts) for:

- `anthropic.RateLimitError` (HTTP 429)
- `anthropic.APIStatusError` with status 5xx
- `anthropic.APIConnectionError`

It honours `retry-after` response headers. 4xx (other than 429) fails fast. If you find a direct `client.messages.create` call in the codebase, that's a bug — wrap it.

### Checkpointing and resume

`ui/results_store.py` provides:

- `begin_run(role, source_filename) -> handle` — opens a run, returns paths for the in-progress and final files plus base metadata. Files are not created until first write.
- `save_checkpoint(handle, results)` — atomic temp-write + rename to `<timestamp>_<source>_INPROGRESS.json`. Called once per completed account.
- `finalize_run(handle, results) -> final_path` — writes the final `<timestamp>_<source>.json`, removes the partial file.
- `load_partial_run(path) -> (results, metadata)` — for resume.
- `find_partial_run(role, source_filename) -> path | None` — newest matching `_INPROGRESS` file.
- `list_runs(role)` — hides `_INPROGRESS` files; UI only shows finalised runs.
- `save_run(...)` is kept as a one-shot back-compat wrapper.

The director consumes this via two new parameters on `run()`:

- `on_account_complete(account_result, all_results_so_far)` — called after every account, used for checkpoint writes.
- `resume_from: list[dict]` — already-completed account results to skip. Keying is `(company.strip().lower(), domain.strip().lower())`.

`ui/home.py` wires this up: on submit, it calls `find_partial_run` for the current source filename and auto-resumes if a partial exists, displaying `Resuming previous run — N account(s) already analysed will be skipped.`

### Scalability status

Single-threaded by design today. The agent contract above (stateless, per-call usage in returns) is what enables a future `ThreadPoolExecutor` over accounts. The next planned phases are: (Phase 2) bounded concurrency + process-wide token-bucket rate limiter; (Phase 3) move `director.run` to a background thread polled from Streamlit `session_state`. Within-account agent fanout is deferred until rate-limit headroom exists (Tier upgrade or token reduction).

Per-account cost is roughly 860 K input tokens for ENT (~40–60 Claude calls). On Tier 1 (~40 K input TPM, ~50 RPM) the practical ceiling is ~10–20 accounts per uninterrupted batch; larger batches will checkpoint reliably but take multiple hours.


---

## Open Questions / Decisions Pending

1. Confirm 3-part skill format for agent prompts
2. Confirm deployment: Docker standalone vs Sonar internal environment
3. LinkedIn data access method (scraping vs official API — compliance risk)
4. ZoomInfo API access — does Sonar have an existing subscription?
5. SFDC integration for Velocity list curation — API access needed
6. Exact ICP criteria for Velocity "create a list" mode
7. Finalize 4-colour personality model to use (DISC, Insights, etc.)
8. Define propensity-to-buy scoring weights per indicator
9. Whether email send is fully automated or always human-in-the-loop

---

## Key Constraints

- Must work within Sonar's IT security environment (Island browser, no direct installs)
- MVP is self-funded — keep infra costs minimal
- No ongoing vendor dependency for Day 2 support — team must be self-sufficient after training
- Personality inference is probabilistic — must be communicated clearly to users as a guide, not ground truth
