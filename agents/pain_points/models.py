"""
Validation helpers for PainPointAgent evidence and score structures.
"""
from __future__ import annotations
from agents.pain_points.config import (
    VALID_PAIN_CATEGORIES,
    VALID_CONFIDENCE,
    VALID_COMPANY_MATCH,
    VALID_SOURCE_TYPES,
    SCORE_CAPS,
    VALID_SCORE_CATEGORIES,
    TOTAL_SCORE_CAP,
)


def validate_evidence_item(item: dict, idx: int) -> dict:
    """Normalise a single evidence item returned by Claude."""
    item.setdefault("id", f"pain_{idx + 1:03d}")
    item.setdefault("category", "code_quality_pain")
    item.setdefault("source_type", "claude_web_search_result")
    item.setdefault("source_url", "")
    item.setdefault("title", "")
    item.setdefault("evidence_text", "")
    item.setdefault("date_posted", None)
    item.setdefault("matched_keywords", [])
    item.setdefault("company_match", "Low")
    item.setdefault("confidence", "Low")

    if item["category"] not in VALID_PAIN_CATEGORIES:
        item["category"] = "code_quality_pain"
    if item["confidence"] not in VALID_CONFIDENCE:
        item["confidence"] = "Low"
    if item["company_match"] not in VALID_COMPANY_MATCH:
        item["company_match"] = "Low"
    if item["source_type"] not in VALID_SOURCE_TYPES:
        item["source_type"] = "claude_web_search_result"
    if not isinstance(item["matched_keywords"], list):
        item["matched_keywords"] = []

    # Coerce counted_in_score — accept bool True or string "true"/"yes"
    counted = item.get("counted_in_score")
    if isinstance(counted, bool):
        item["counted_in_score"] = counted
    elif isinstance(counted, str) and counted.lower() in ("true", "yes", "1"):
        item["counted_in_score"] = True
    else:
        item["counted_in_score"] = False

    # Low-confidence or no-URL items must not be counted
    if item["confidence"] == "Low" and not item["source_url"]:
        item["counted_in_score"] = False

    return item


def validate_score_breakdown(breakdown: dict, evidence: list[dict]) -> dict:
    """
    Clamp breakdown values to caps and zero out categories
    that have no counted evidence backing them.
    """
    if not isinstance(breakdown, dict):
        breakdown = {}

    # Clamp to caps
    for cat in VALID_SCORE_CATEGORIES:
        try:
            breakdown[cat] = min(float(breakdown.get(cat, 0)), SCORE_CAPS[cat])
        except (TypeError, ValueError):
            breakdown[cat] = 0.0

    # Any category with a non-zero score must have at least one
    # counted evidence item to back it. Zero it out otherwise.
    has_counted = any(e.get("counted_in_score") for e in evidence)
    if not has_counted:
        for cat in VALID_SCORE_CATEGORIES:
            breakdown[cat] = 0.0

    breakdown["total"] = min(
        sum(breakdown[cat] for cat in VALID_SCORE_CATEGORIES),
        TOTAL_SCORE_CAP,
    )
    return breakdown
