from __future__ import annotations

VALID_STATUSES = frozenset({"completed", "partial", "no_data", "error"})
VALID_CONFIDENCE = frozenset({"High", "Medium", "Low"})
VALID_SOURCE_TYPES = frozenset({
    "company_website", "newsroom", "investor_relations", "news", "linkedin",
})
VALID_SOURCE_STATUSES = frozenset({"fetched", "searched", "failed", "blocked"})

SNAPSHOT_FIELDS = (
    "what_they_do",
    "who_they_sell_to",
    "regions_scale",
    "business_model",
    "key_acquisition",
    "strategic_direction",
    "ai_posture",
)
