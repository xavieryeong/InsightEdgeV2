VALID_TECH_CATEGORIES = [
    "relevant_languages",
    "ci_cd_maturity",
    "cloud_native_presence",
    "security_tooling_signal",
    "engineering_visibility",
]

SCORE_CAPS = {
    "relevant_languages":      3.0,
    "ci_cd_maturity":          2.5,
    "cloud_native_presence":   2.0,
    "security_tooling_signal": 1.5,
    "engineering_visibility":  1.0,
}

VALID_SCORE_CATEGORIES = list(SCORE_CAPS.keys())
TOTAL_SCORE_CAP = 10.0

VALID_STATUSES   = {"completed", "partial", "no_data", "error"}
VALID_CONFIDENCE = {"High", "Medium", "Low"}

VALID_SOURCE_TYPES = {
    "github",
    "engineering_blog",
    "tech_listing",
    "developer_docs",
    "claude_web_search_result",
}

# Maps evidence category → grouped list key in the output dict
CATEGORY_TO_GROUP = {
    "relevant_languages":      "languages",
    "ci_cd_maturity":          "cicd_tools",
    "cloud_native_presence":   "cloud",
    "security_tooling_signal": "security_tools",
}

MAX_SEARCH_ITERATIONS = 10
