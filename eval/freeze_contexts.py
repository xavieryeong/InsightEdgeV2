"""
freeze_contexts.py

Reads existing result JSONs and reconstructs a frozen evidence context string
per agent per company. Outputs to eval/frozen_contexts/{company_id}/{agent}.txt

These frozen contexts are replayed into Call 2 (scoring/structuring) across
models — Haiku, Sonnet, Opus, gpt-4o — so the only variable is the model.

Usage:
    python eval/freeze_contexts.py
"""

import json
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN_SET = os.path.join(REPO_ROOT, "eval", "golden_set.json")
OUT_DIR = os.path.join(REPO_ROOT, "eval", "frozen_contexts")

SCOREABLE_AGENTS = {
    "tech_stack",
    "hiring_patterns",
    "public_news",
    "regulatory_impact",
    "pain_points",
}


def reconstruct_tech_stack(evidence: list) -> str:
    lines = []
    for ev in evidence:
        lines.append(
            f"[TECH] {ev.get('name', '?')} | category={ev.get('category', '?')} "
            f"| source={ev.get('source_type', '?')} | url={ev.get('source_url', '')}"
        )
        if ev.get("evidence_text"):
            lines.append(f"  Evidence: {ev['evidence_text']}")
        if ev.get("repo_url"):
            lines.append(f"  Repo: {ev['repo_url']}")
        lines.append(f"  Confidence: {ev.get('confidence', '?')}")
        lines.append("")
    return "\n".join(lines)


def reconstruct_hiring(evidence: list) -> str:
    lines = []
    for ev in evidence:
        lines.append(
            f"[HIRING] type={ev.get('type', '?')} | value={ev.get('value', '?')} "
            f"| source={ev.get('source_type', '?')} | url={ev.get('source_url', '')}"
        )
        if ev.get("title"):
            lines.append(f"  Title: {ev['title']}")
        if ev.get("evidence_text"):
            lines.append(f"  Evidence: {ev['evidence_text']}")
        if ev.get("date_posted"):
            lines.append(f"  Date posted: {ev['date_posted']}")
        lines.append(f"  Confidence: {ev.get('confidence', '?')}")
        lines.append("")
    return "\n".join(lines)


def reconstruct_news(evidence: list) -> str:
    lines = []
    for ev in evidence:
        lines.append(
            f"[NEWS] signal={ev.get('signal_type', '?')} "
            f"| source={ev.get('source_type', '?')} | url={ev.get('url', '')}"
        )
        if ev.get("title"):
            lines.append(f"  Title: {ev['title']}")
        if ev.get("snippet"):
            lines.append(f"  Snippet: {ev['snippet']}")
        if ev.get("published_date"):
            lines.append(f"  Published: {ev['published_date']} ({ev.get('days_ago', '?')} days ago)")
        if ev.get("article_summary"):
            lines.append(f"  Summary: {ev['article_summary']}")
        lines.append(f"  Confidence: {ev.get('confidence', '?')}")
        lines.append("")
    return "\n".join(lines)


def reconstruct_regulatory(evidence: list) -> str:
    lines = []
    for ev in evidence:
        lines.append(
            f"[REGULATORY] type={ev.get('type', '?')} | value={ev.get('value', '?')} "
            f"| regulation={ev.get('regulation', '?')} | regulator={ev.get('regulator', '?')}"
        )
        lines.append(
            f"  Source: {ev.get('source_type', '?')} | url={ev.get('source_url', '')}"
        )
        if ev.get("evidence_text"):
            lines.append(f"  Evidence: {ev['evidence_text']}")
        lines.append(f"  Confidence: {ev.get('confidence', '?')}")
        lines.append("")
    return "\n".join(lines)


def reconstruct_pain_points(evidence: list) -> str:
    lines = []
    for ev in evidence:
        lines.append(
            f"[PAIN] category={ev.get('category', '?')} "
            f"| source={ev.get('source_type', '?')} | url={ev.get('source_url', '')}"
        )
        if ev.get("title"):
            lines.append(f"  Title: {ev['title']}")
        if ev.get("evidence_text"):
            lines.append(f"  Evidence: {ev['evidence_text']}")
        if ev.get("date_posted"):
            lines.append(f"  Date: {ev['date_posted']}")
        lines.append(f"  Confidence: {ev.get('confidence', '?')}")
        lines.append("")
    return "\n".join(lines)


RECONSTRUCTORS = {
    "tech_stack": reconstruct_tech_stack,
    "hiring_patterns": reconstruct_hiring,
    "public_news": reconstruct_news,
    "regulatory_impact": reconstruct_regulatory,
    "pain_points": reconstruct_pain_points,
}


def load_result_file(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("results", [])


def find_company(results: list, company_name: str, domain: str):
    name_lower = company_name.strip().lower()
    domain_lower = domain.strip().lower()
    for r in results:
        r_name = r.get("company", "").strip().lower()
        r_domain = r.get("domain", "").strip().lower()
        if r_name == name_lower or domain_lower in r_domain or r_domain in domain_lower:
            return r
    return None


def freeze_company(entry: dict, results_cache: dict) -> dict:
    """Return {agent_key: context_text} for all scoreable agents."""
    source_file = os.path.join(REPO_ROOT, entry["source_file"])

    if source_file not in results_cache:
        results_cache[source_file] = load_result_file(source_file)

    results = results_cache[source_file]
    record = find_company(results, entry["company"], entry["domain"])

    if record is None:
        print(f"  WARNING: {entry['company']} not found in {entry['source_file']}")
        return {}

    signals = record.get("signals", {})
    contexts = {}

    for agent_key, reconstructor in RECONSTRUCTORS.items():
        agent_data = signals.get(agent_key)
        if not agent_data or not isinstance(agent_data, dict):
            continue

        evidence = agent_data.get("evidence", [])
        if not evidence:
            continue

        header = (
            f"Company: {entry['company']}\n"
            f"Domain: {entry['domain']}\n"
            f"Industry: {record.get('industry', entry['industry'])}\n"
            f"Country: {record.get('country', entry['region'])}\n"
            f"Agent: {agent_key}\n"
            f"Evidence items: {len(evidence)}\n"
            f"{'=' * 60}\n\n"
        )
        contexts[agent_key] = header + reconstructor(evidence)

    return contexts


def main():
    golden = json.load(open(GOLDEN_SET, encoding="utf-8"))
    results_cache = {}
    total_files = 0
    total_skipped = 0

    for entry in golden:
        cid = entry["id"]
        out_dir = os.path.join(OUT_DIR, cid)
        os.makedirs(out_dir, exist_ok=True)

        print(f"Processing {entry['company']} ({cid})...")
        contexts = freeze_company(entry, results_cache)

        if not contexts:
            total_skipped += 1
            continue

        for agent_key, text in contexts.items():
            out_path = os.path.join(out_dir, f"{agent_key}.txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            total_files += 1

        print(f"  -> {len(contexts)} agent contexts saved: {list(contexts.keys())}")

    print(f"\nDone. {total_files} context files written, {total_skipped} companies skipped.")
    print(f"Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
