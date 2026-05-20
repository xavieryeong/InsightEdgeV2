# Classification thresholds (total max = 10, 5 dimensions × 2 each)
LEADER_THRESHOLD = 7
LAGGARD_THRESHOLD = 3

# Number of skeptic flags to be considered "dominant" (overrides high score)
SKEPTIC_DOMINANT_COUNT = 2

# ── Dimension: AI / Innovation News ──────────────────────────────────────────

AI_INNOVATION_LEADER_KEYWORDS = [
    "ai initiative", "generative ai", "ai strategy", "ai product",
    "ai partnership", "machine learning platform", "mlops",
    "cloud transformation", "digital transformation", "ai adoption",
    "large language model", "llm", "ai-powered", "ai-first",
    "innovation", "emerging technology", "ai roadmap", "ai platform",
    "tech transformation",
]

AI_INNOVATION_SKEPTIC_KEYWORDS = [
    "responsible ai", "ai governance", "ai risk", "ai ethics",
    "privacy concerns", "regulatory caution", "ai compliance",
    "questioning ai", "ai roi", "slow adoption", "ai safety",
    "ai oversight", "data privacy",
]

# ── Dimension: Leadership Messaging ──────────────────────────────────────────

LEADERSHIP_LEADER_KEYWORDS = [
    "ai strategy", "digital transformation", "innovation agenda",
    "engineering excellence", "technology leadership", "cloud-first",
    "platform modernization", "new cto", "new ciso", "ai vision",
    "innovation-focused", "tech transformation", "ai roadmap",
    "engineering culture", "developer productivity",
]

LEADERSHIP_SKEPTIC_KEYWORDS = [
    "ai risk", "ai governance", "data privacy", "compliance focus",
    "responsible ai", "ai oversight", "ai caution", "governance framework",
    "risk management", "regulatory compliance",
]

# ── Skeptic flag keywords (scanned across all evidence text) ─────────────────

SKEPTIC_FLAG_KEYWORDS = [
    "responsible ai",
    "ai governance",
    "ai risk",
    "regulatory caution",
    "privacy concerns",
    "compliance-heavy",
    "questioning ai roi",
    "slow adoption",
    "security-first transformation",
    "ai ethics",
    "ai safety",
    "data privacy",
    "ai oversight",
    "ai caution",
    "governance framework",
]

# ── Hiring categories mapped to leader / skeptic signals ─────────────────────

LEADER_HIRING_CATEGORIES = frozenset({
    # Current hiring agent category keys
    "devsecops_appsec", "devops_platform", "software_engineering_growth", "cloud_infrastructure",
    # Legacy keys
    "devsecops", "devops", "cloud", "software_engineer",
})
SKEPTIC_HIRING_CATEGORIES = frozenset({
    # security/compliance-only hiring (without dev categories) signals risk-focus
    "security_compliance", "security",
})

# ── News categories mapped to each dimension ─────────────────────────────────

NEWS_AI_LEADER_CATEGORIES = frozenset({
    # Current news agent category keys
    "cloud_ai_transformation", "product_platform_launch", "engineering_investment",
    "cybersecurity_incident",  # security incident = urgent need for code security → Sonar signal
    # Legacy keys
    "cloud_ai_initiative", "product_launch", "acquisition", "hiring_wave",
})
NEWS_SKEPTIC_CATEGORIES = frozenset({
    "compliance_regulatory",
})
NEWS_LEADERSHIP_CATEGORIES = frozenset({
    "leadership_change",
})
