VALID_HIRING_CATEGORIES = [
    "devsecops_appsec",
    "devops_platform",
    "software_engineering_growth",
    "cloud_infrastructure",
    "security_compliance",
]

SCORE_CAPS = {
    "devsecops_appsec":            3.0,
    "devops_platform":             2.5,
    "software_engineering_growth": 2.0,
    "cloud_infrastructure":        1.5,
    "security_compliance":         1.0,
    "recency_bonus":               0.5,
}

VALID_SCORE_CATEGORIES = list(SCORE_CAPS.keys())
TOTAL_SCORE_CAP = 10.0

VALID_STATUSES    = {"completed", "partial", "no_data", "error"}
VALID_CONFIDENCE  = {"High", "Medium", "Low"}
VALID_COMPANY_MATCH = {"High", "Medium", "Low"}

VALID_SOURCE_TYPES = {
    "careers_page",
    "ats_platform",
    "linkedin",
    "job_board",
    "claude_web_search_result",
}

MAX_SEARCH_ITERATIONS = 10
