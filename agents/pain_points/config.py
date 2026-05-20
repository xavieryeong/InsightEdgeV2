VALID_PAIN_CATEGORIES = [
    "security_incident_pain",
    "code_quality_pain",
    "static_analysis_pain",
    "ci_cd_integration_pain",
    "technical_debt_pain",
    "developer_velocity_pain",
    "competitor_tooling_pain",
    "sonar_specific_pain",
]

# score_breakdown category caps
SCORE_CAPS = {
    "company_linked_pain":      3.0,
    "security_quality_urgency": 2.5,
    "delivery_pressure":        2.0,
    "sonar_or_competitor_pain": 1.5,
    "recency_repeat_bonus":     1.0,
}

VALID_SCORE_CATEGORIES = list(SCORE_CAPS.keys())
TOTAL_SCORE_CAP = 10.0

VALID_STATUSES   = {"completed", "partial", "no_data", "error"}
VALID_CONFIDENCE = {"High", "Medium", "Low"}
VALID_COMPANY_MATCH = {"High", "Medium", "Low"}

VALID_SOURCE_TYPES = {
    "github",
    "stackoverflow",
    "reddit",
    "sonar_community",
    "company_engineering_blog",
    "company_forum",
    "claude_web_search_result",
}

MAX_SEARCH_ITERATIONS = 10
