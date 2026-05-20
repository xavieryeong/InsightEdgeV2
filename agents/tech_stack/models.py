"""
Validation helpers for TechStackAgent evidence and score structures.
"""
from __future__ import annotations

from agents.tech_stack.config import (
    VALID_TECH_CATEGORIES,
    VALID_CONFIDENCE,
    VALID_SOURCE_TYPES,
    SCORE_CAPS,
    VALID_SCORE_CATEGORIES,
    TOTAL_SCORE_CAP,
    CATEGORY_TO_GROUP,
)


def validate_evidence_item(item: dict, idx: int) -> dict:
    """Normalise a single evidence item returned by Claude."""
    item.setdefault("id", f"tech_{idx + 1:03d}")
    item.setdefault("category", "relevant_languages")
    item.setdefault("name", "")
    item.setdefault("source_type", "claude_web_search_result")
    item.setdefault("source_url", "")
    item.setdefault("evidence_text", "")
    item.setdefault("confidence", "Low")

    if item["category"] not in VALID_TECH_CATEGORIES:
        item["category"] = "relevant_languages"
    if item["confidence"] not in VALID_CONFIDENCE:
        item["confidence"] = "Low"
    if item["source_type"] not in VALID_SOURCE_TYPES:
        item["source_type"] = "claude_web_search_result"

    # Coerce counted_in_score
    counted = item.get("counted_in_score")
    if isinstance(counted, bool):
        item["counted_in_score"] = counted
    elif isinstance(counted, str) and counted.lower() in ("true", "yes", "1"):
        item["counted_in_score"] = True
    else:
        item["counted_in_score"] = False

    # Low-confidence with no URL must not be counted
    if item["confidence"] == "Low" and not item["source_url"]:
        item["counted_in_score"] = False

    # repo_url alias for backward compatibility with account_render.py
    item.setdefault("repo_url", item["source_url"])

    return item


def validate_grouped_item(item: dict) -> dict:
    """Normalise a single item inside languages / cicd_tools / cloud / security_tools."""
    item.setdefault("name", "")
    item.setdefault("confidence", "Low")
    if item["confidence"] not in VALID_CONFIDENCE:
        item["confidence"] = "Low"
    if not isinstance(item.get("evidence_ids"), list):
        item["evidence_ids"] = []
    return item


def rebuild_grouped_lists(evidence: list[dict]) -> dict[str, list[dict]]:
    """
    Build languages / cicd_tools / cloud / security_tools from evidence items.
    Used when Claude omits or returns empty grouped lists.
    Deduplicates by name, keeping highest confidence per name.
    """
    _CONF_ORDER = {"High": 3, "Medium": 2, "Low": 1}

    groups: dict[str, dict[str, dict]] = {g: {} for g in CATEGORY_TO_GROUP.values()}

    for ev in evidence:
        group_key = CATEGORY_TO_GROUP.get(ev.get("category", ""))
        if not group_key:
            continue
        name = ev.get("name", "").strip()
        if not name:
            continue
        existing = groups[group_key].get(name)
        ev_conf_rank = _CONF_ORDER.get(ev.get("confidence", "Low"), 0)
        if existing is None or ev_conf_rank > _CONF_ORDER.get(existing["confidence"], 0):
            groups[group_key][name] = {
                "name": name,
                "confidence": ev.get("confidence", "Low"),
                "evidence_ids": [ev["id"]],
            }
        else:
            existing["evidence_ids"].append(ev["id"])

    return {key: list(val.values()) for key, val in groups.items()}


def validate_score_breakdown(breakdown: dict, evidence: list[dict]) -> dict:
    """
    Clamp breakdown values to caps and zero everything if no counted evidence exists.
    """
    if not isinstance(breakdown, dict):
        breakdown = {}

    for cat in VALID_SCORE_CATEGORIES:
        try:
            breakdown[cat] = min(float(breakdown.get(cat, 0)), SCORE_CAPS[cat])
        except (TypeError, ValueError):
            breakdown[cat] = 0.0

    has_counted = any(e.get("counted_in_score") for e in evidence)
    if not has_counted:
        for cat in VALID_SCORE_CATEGORIES:
            breakdown[cat] = 0.0

    breakdown["total"] = min(
        sum(breakdown[cat] for cat in VALID_SCORE_CATEGORIES),
        TOTAL_SCORE_CAP,
    )
    return breakdown
