"""
run_ragas.py

Takes the Promptfoo output JSON and runs RAGAS faithfulness metric
on each (question, answer, contexts) triple.

Usage:
    python eval/run_ragas.py --input eval/promptfoo_output.json --out eval/ragas_results.json

Install:
    pip install ragas datasets langchain-anthropic

RAGAS version verified: 0.2.x (current as of mid-2026)
Faithfulness is the priority metric: does the scored output stay grounded
in the retrieved evidence, with no invented signals?
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Load .env from repo root so API keys don't need to be set manually each session
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass


def load_promptfoo_output(path: str) -> list:
    """Parse Promptfoo results JSON into eval triples."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Promptfoo output format: {"results": {"results": [...]}}
    # each result has: vars, response.output, provider
    raw_results = (
        data.get("results", {}).get("results", [])
        if isinstance(data.get("results"), dict)
        else data.get("results", [])
    )

    triples = []
    for r in raw_results:
        vars_ = r.get("vars", {})
        output = r.get("response", {}).get("output", "")
        provider = r.get("provider", {}).get("label", r.get("provider", "unknown"))

        if not output:
            continue

        triples.append({
            "company": vars_.get("company", ""),
            "agent": vars_.get("agent", ""),
            "provider": provider,
            "signal_band": vars_.get("signal_band", ""),
            "known_score": vars_.get("known_score", 0),
            # RAGAS fields
            "user_input": f"Score buying signals for {vars_.get('company', '')} using the {vars_.get('agent', '')} agent.",
            "response": output,
            "retrieved_contexts": [vars_.get("frozen_context", "")],
        })

    return triples


def run_ragas(triples: list, out_path: str):
    try:
        from ragas import evaluate
        from ragas.metrics.collections import Faithfulness
        from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
        from ragas.llms import llm_factory
        from openai import OpenAI
    except ImportError as e:
        print(f"ERROR: Missing dependency — {e}")
        print("Install with: pip install ragas datasets openai")
        sys.exit(1)

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        print("ERROR: OPENAI_API_KEY not set")
        sys.exit(1)

    # RAGAS collections metrics require InstructorLLM via llm_factory (not LangChain adapters)
    openai_client = OpenAI(api_key=openai_key)
    llm = llm_factory("gpt-4o-mini", client=openai_client)

    # Group by provider so we get per-model RAGAS scores
    by_provider: dict[str, list] = {}
    for t in triples:
        by_provider.setdefault(t["provider"], []).append(t)

    all_results = {}

    for provider, items in by_provider.items():
        print(f"\nRunning RAGAS for provider: {provider} ({len(items)} samples)...")

        samples = [
            SingleTurnSample(
                user_input=item["user_input"],
                response=item["response"],
                retrieved_contexts=item["retrieved_contexts"],
            )
            for item in items
        ]

        dataset = EvaluationDataset(samples=samples)

        try:
            metric = Faithfulness(llm=llm)
            result = evaluate(
                dataset=dataset,
                metrics=[metric],
                llm=llm,
            )
            # Use result.scores (list of dicts) — avoids NumPy 2.0 / pandas conflict
            faith_scores = [s.get("faithfulness", 0) for s in result.scores]
            avg_faith = sum(faith_scores) / len(faith_scores) if faith_scores else 0
            all_results[provider] = {
                "sample_count": len(items),
                "faithfulness": round(avg_faith, 4),
                "per_sample": [
                    {
                        "company": items[i]["company"],
                        "agent": items[i]["agent"],
                        "signal_band": items[i]["signal_band"],
                        "known_score": items[i]["known_score"],
                        "faithfulness": round(float(faith_scores[i]), 4),
                    }
                    for i in range(len(items))
                ],
            }
            print(f"  faithfulness={avg_faith:.3f}")
        except Exception as e:
            print(f"  ERROR for {provider}: {e}")
            all_results[provider] = {"error": str(e)}

    Path(out_path).write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRAGAS results written to {out_path}")
    return all_results


def print_summary(results: dict):
    print("\n" + "=" * 60)
    print("RAGAS SUMMARY")
    print("=" * 60)
    print(f"{'Provider':<20} {'Faithfulness':>14} {'Samples':>8}")
    print("-" * 46)
    for provider, r in results.items():
        if "error" in r:
            print(f"{provider:<20} {'ERROR':>14}")
        else:
            print(f"{provider:<20} {r['faithfulness']:>14.3f} {r['sample_count']:>8}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Promptfoo output JSON file")
    parser.add_argument("--out", default="eval/ragas_results.json", help="Output path")
    parser.add_argument("--max-samples", type=int, default=0, help="Cap samples per provider (0 = no cap)")
    args = parser.parse_args()

    print(f"Loading Promptfoo results from {args.input}...")
    triples = load_promptfoo_output(args.input)
    if args.max_samples:
        from collections import defaultdict
        by_prov = defaultdict(list)
        for t in triples:
            by_prov[t["provider"]].append(t)
        triples = [t for items in by_prov.values() for t in items[:args.max_samples]]
        print(f"Capped to {args.max_samples} samples per provider ({len(triples)} total)")
    else:
        print(f"Loaded {len(triples)} (company, agent, provider) triples")

    if not triples:
        print("ERROR: No triples found. Check that --input points to a valid Promptfoo output JSON.")
        sys.exit(1)

    results = run_ragas(triples, args.out)
    print_summary(results)


if __name__ == "__main__":
    main()
