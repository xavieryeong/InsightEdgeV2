from __future__ import annotations

VALID_STATUSES = frozenset({"completed", "partial", "no_data", "error"})
VALID_CONFIDENCE = frozenset({"High", "Medium", "Low"})

VALID_PRIMARY_COLOURS = frozenset({"Red", "Blue", "Green", "Yellow", "Unknown"})
VALID_SECONDARY_COLOURS = frozenset({"Red", "Blue", "Green", "Yellow", "None"})

# Roles Claude should search for, in priority order
TARGET_ROLES = [
    "CTO",
    "VP Engineering",
    "Head of DevOps",
    "Head of Platform Engineering",
    "Head of AppSec",
    "CISO",
    "Engineering Director",
]

# Colour energy traits — used in prompt and for reference
COLOUR_TRAITS: dict[str, list[str]] = {
    "Red":    ["Competitive", "Results-Oriented", "Strong-Willed", "Risk-Taker", "Direct"],
    "Blue":   ["Analytical", "Diplomatic", "Precise", "Questioning", "Conventional"],
    "Green":  ["Patient", "Steady", "Systematic", "Good Listener", "Caring"],
    "Yellow": ["Expressive", "Inspiring", "Trusting", "Talkative", "Sociable"],
}

VALID_SOURCE_TYPES = frozenset({
    "company_website", "linkedin", "news", "press_release", "conference", "blog",
})
VALID_SOURCE_STATUSES = frozenset({"fetched", "searched", "failed", "blocked"})
