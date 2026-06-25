"""
generate_promptfoo_tests.py

Reads golden_set.json + frozen_contexts/ and generates:
  eval/promptfoo_tests.json   — array of test cases for promptfoo

Each test case:
  - vars.system_prompt  : content of agents/{agent}/prompt.md
  - vars.frozen_context : content of frozen_contexts/{company_id}/{agent}.txt
  - vars.company        : company name
  - vars.agent          : agent key
  - vars.known_score    : production score (soft reference for the judge)
  - vars.signal_band    : high / medium / low / zero

Usage:
    python eval/generate_promptfoo_tests.py
"""

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
GOLDEN_SET = REPO_ROOT / "eval" / "golden_set.json"
FROZEN_DIR = REPO_ROOT / "eval" / "frozen_contexts"
AGENTS_DIR = REPO_ROOT / "agents"
OUT_FILE = REPO_ROOT / "eval" / "promptfoo_tests.json"

AGENT_PROMPT_FILES = {
    "tech_stack": AGENTS_DIR / "tech_stack" / "prompt.md",
    "hiring_patterns": AGENTS_DIR / "hiring" / "prompt.md",
    "public_news": AGENTS_DIR / "news" / "prompt.md",
    "regulatory_impact": AGENTS_DIR / "regulatory" / "prompt.md",
    "pain_points": AGENTS_DIR / "pain_points" / "prompt.md",
}

# Prefix appended to the frozen context so the model knows not to search
FROZEN_PREAMBLE = (
    "## IMPORTANT: Evidence pre-retrieved\n\n"
    "The web search phase has already been completed. "
    "The full retrieved evidence is provided below. "
    "Do NOT call web_search. Do NOT invent additional evidence. "
    "Score and structure ONLY the evidence provided.\n\n"
    "## Pre-retrieved Evidence\n\n"
)


def load_system_prompts() -> dict:
    prompts = {}
    for agent_key, path in AGENT_PROMPT_FILES.items():
        if path.exists():
            prompts[agent_key] = path.read_text(encoding="utf-8")
        else:
            print(f"WARNING: prompt file not found: {path}")
    return prompts


def main():
    golden = json.loads(GOLDEN_SET.read_text(encoding="utf-8"))
    system_prompts = load_system_prompts()
    tests = []

    for entry in golden:
        cid = entry["id"]
        ctx_dir = FROZEN_DIR / cid

        if not ctx_dir.exists():
            print(f"SKIP {cid}: no frozen_contexts directory")
            continue

        for agent_key, system_prompt in system_prompts.items():
            ctx_file = ctx_dir / f"{agent_key}.txt"
            if not ctx_file.exists():
                continue

            frozen_context = ctx_file.read_text(encoding="utf-8")

            tests.append({
                "description": f"{cid}__{agent_key}",
                "vars": {
                    "system_prompt": system_prompt,
                    "frozen_context": FROZEN_PREAMBLE + frozen_context,
                    "company": entry["company"],
                    "agent": agent_key,
                    "known_score": entry["known_score"],
                    "signal_band": entry["signal_band"],
                    "industry": entry["industry"],
                    "region": entry["region"],
                },
                "assert": [
                    {
                        "type": "llm-rubric",
                        "metric": "faithfulness",
                        "threshold": 0.4,
                        "value": (
                            "Every signal or finding mentioned in the output must be "
                            "directly supported by evidence in the frozen_context. "
                            "The model must NOT invent signals, companies, URLs, job titles, "
                            "regulations, or dates that are not present in the provided evidence. "
                            "Note: dates and URLs that appear in the evidence are valid to reference. "
                            "Score 1.0 if every claim maps to explicit evidence. "
                            "Score 0.5 if there are minor unsupported inferences (acceptable). "
                            "Score 0.0 if the model clearly fabricates evidence not in the context."
                        ),
                    },
                    {
                        "type": "llm-rubric",
                        "metric": "signal_accuracy",
                        "threshold": 0.6,
                        "value": (
                            "Did the model identify the key signals present in the evidence? "
                            "Score 1.0 if all major signals in the evidence are captured in the output. "
                            "Score 0.5 if some significant signals were missed. "
                            "Score 0.0 if the output is mostly empty or misses obvious signals."
                        ),
                    },
                    {
                        "type": "llm-rubric",
                        "metric": "score_calibration",
                        "threshold": 0.6,
                        # Each agent scores 0-10. Use signal_band as the calibration reference.
                        # Rubric is intentionally simple: zero-band should score low, high-band high.
                        "value": (
                            f"signal_band for this company+agent is '{entry['signal_band']}'. "
                            "The output may be wrapped in ```json fences — look inside them. "
                            "Find the top-level field named exactly 'score' (a number 0–10). "
                            "For signal_band='zero': score should be 0–2. "
                            "For signal_band='low': score should be 1–5. "
                            "For signal_band='medium': score should be 4–8. "
                            "For signal_band='high': score should be 6–10. "
                            "Score this assertion 1.0 if the 'score' field is in the expected range, "
                            "0.5 if slightly outside, 0.0 if badly wrong or missing."
                        ),
                    },
                ],
            })

    OUT_FILE.write_text(json.dumps(tests, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Generated {len(tests)} test cases -> {OUT_FILE}")


if __name__ == "__main__":
    main()
