PRIMARY_WINDOW_DAYS = 90     # 3 months — the only scoring window for Velocity
RECENCY_BONUS_DAYS  = 30     # 1 month — tightest recency window for bonus point

# Claude web search is triggered when scored evidence is below this threshold
WEAK_EVIDENCE_THRESHOLD = 3

NEWS_PATHS = [
    "/newsroom",
    "/press",
    "/press-releases",
    "/news",
    "/investor-relations",
    "/ir",
    "/about/news",
    "/about/press",
    "/blog/news",
    "/media",
]

# Keywords that indicate Sonar-relevant technology or engineering news signals
# Only technology/engineering-related signals are valid for Velocity.
URGENCY_KEYWORD_GROUPS = {
    "cybersecurity_incident": [
        "breach", "data breach", "cyberattack", "cyber attack", "ransomware",
        "vulnerability", "CVE", "hacked", "security incident", "data leak",
        "data exposure", "zero-day", "zero day", "malware", "phishing attack",
        "supply chain attack", "compromised", "unauthorized access",
        "software security incident", "vulnerability disclosure",
    ],
    "cloud_ai_transformation": [
        "cloud migration", "digital transformation", "AI initiative",
        "generative AI", "AI platform", "platform engineering",
        "cloud-native", "SaaS migration", "AI adoption", "AI strategy",
        "machine learning platform", "MLOps", "cloud investment",
        "DevOps transformation", "CI/CD modernization",
        "software delivery modernization", "modernization program",
        "engineering transformation", "cloud-native transformation",
    ],
    "product_platform_launch": [
        "launches", "launch", "announces new", "major release",
        "general availability", "new platform", "new product",
        "new version", "engineering milestone", "developer platform",
        "platform launch", "product engineering milestone",
    ],
    "engineering_investment": [
        "engineering center", "R&D expansion", "product engineering investment",
        "engineering hiring announcement", "scaling engineering",
        "expanding engineering", "new development center",
        "software development investment", "developer hiring",
    ],
    "leadership_change": [
        "appoints", "appointed", "names new CTO", "names new CISO",
        "new CTO", "new CISO", "new VP Engineering", "joins as CTO",
        "joins as CISO", "Chief Technology Officer",
        "Chief Information Security Officer", "VP of Engineering",
        "Head of Platform", "CTO departs", "CISO leaves",
    ],
}

# Scoring per category (binary — detected or not within the 90-day window)
SCORING = {
    "cybersecurity_incident":  3.0,
    "cloud_ai_transformation": 2.5,
    "product_platform_launch": 2.0,
    "engineering_investment":  1.5,
    "leadership_change":       0.5,
    "recency_bonus":           0.5,   # any signal within RECENCY_BONUS_DAYS
    "total_cap":               10.0,
}
