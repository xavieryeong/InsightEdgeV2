from __future__ import annotations

# Score category caps
SCORE_CAPS: dict[str, float] = {
    "active_fine_lawsuit": 3.0,
    "specific_regulation_applies": 2.5,
    "compliance_audit": 2.0,
    "regulated_industry": 1.5,
    "regional_regulator_relevance": 1.0,
    "general_regulatory_mention": 0.5,
}

TOTAL_SCORE_CAP: float = 10.0
INDUSTRY_ONLY_SCORE_CAP: float = 3.0

VALID_SCORE_CATEGORIES: tuple[str, ...] = tuple(SCORE_CAPS.keys())
VALID_STATUSES = frozenset({"completed", "partial", "no_data", "error"})
VALID_CONFIDENCE = frozenset({"High", "Medium", "Low"})
VALID_EVIDENCE_TYPES = frozenset(SCORE_CAPS.keys())
VALID_SOURCE_TYPES = frozenset({
    "official_regulator_website",
    "company_website",
    "public_news",
    "claude_web_search_result",
    "industry_mapping",
})
VALID_SOURCE_STATUSES = frozenset({"searched", "fetched", "failed", "blocked"})

# Country → (short name, full name, website) for financial regulators
COUNTRY_REGULATOR_MAP: dict[str, tuple[str, str, str]] = {
    "singapore": ("MAS", "Monetary Authority of Singapore", "https://mas.gov.sg"),
    "indonesia": ("OJK", "Otoritas Jasa Keuangan", "https://ojk.go.id"),
    "india": ("RBI", "Reserve Bank of India", "https://rbi.org.in"),
    "malaysia": ("BNM", "Bank Negara Malaysia", "https://bnm.gov.my"),
    "philippines": ("BSP", "Bangko Sentral ng Pilipinas", "https://bsp.gov.ph"),
    "thailand": ("BOT", "Bank of Thailand", "https://bot.or.th"),
    "hong kong": ("HKMA", "Hong Kong Monetary Authority", "https://hkma.gov.hk"),
    "australia": ("APRA", "Australian Prudential Regulation Authority", "https://apra.gov.au"),
    "united kingdom": ("FCA", "Financial Conduct Authority", "https://fca.org.uk"),
    "uk": ("FCA", "Financial Conduct Authority", "https://fca.org.uk"),
    "european union": ("EBA", "European Banking Authority", "https://eba.europa.eu"),
    "eu": ("EBA", "European Banking Authority", "https://eba.europa.eu"),
    "united states": ("FFIEC", "Federal Financial Institutions Examination Council", "https://ffiec.gov"),
    "us": ("FFIEC", "Federal Financial Institutions Examination Council", "https://ffiec.gov"),
    "usa": ("FFIEC", "Federal Financial Institutions Examination Council", "https://ffiec.gov"),
}

# Industries that trigger central bank / financial regulator lookup
FINANCIAL_INDUSTRIES = frozenset({
    "financial_services", "banking", "fintech", "insurance",
    "payments", "retail_payments", "lending", "card_issuing",
    "acquiring", "merchant_services", "investment_banking",
    "wealth_management", "brokerage", "neobank",
})

# Industry → applicable regulatory frameworks
INDUSTRY_REGULATION_MAP: dict[str, list[str]] = {
    "financial_services": ["PCI DSS 4.0", "ISO 27001", "SOC 2", "GDPR", "DORA"],
    "banking": ["PCI DSS 4.0", "ISO 27001", "DORA", "NIS2", "Basel III operational risk"],
    "fintech": ["PCI DSS 4.0", "ISO 27001", "SOC 2", "GDPR", "DORA"],
    "payments": ["PCI DSS 4.0", "ISO 27001", "GDPR"],
    "retail_payments": ["PCI DSS 4.0", "ISO 27001"],
    "insurance": ["SOC 2", "ISO 27001", "GDPR", "DORA"],
    "healthcare": ["HIPAA", "HITRUST", "ISO 27001", "SOC 2"],
    "medical_devices": ["HIPAA", "IEC 62304", "ISO 13485", "ISO 27001"],
    "manufacturing": ["MISRA", "IEC 62443", "ISO 27001"],
    "automotive": ["MISRA C/C++", "ISO 26262", "IEC 62443", "ISO 27001"],
    "aerospace": ["DO-178C", "IEC 62443", "ISO 27001"],
    "public_sector": ["FedRAMP", "CMMC", "NIST SP 800-53"],
    "government": ["FedRAMP", "CMMC", "NIST SP 800-53"],
    "defense": ["CMMC", "NIST SP 800-171", "ITAR"],
    "saas": ["SOC 2", "ISO 27001", "GDPR", "NIS2"],
    "technology": ["SOC 2", "ISO 27001", "GDPR", "NIS2"],
    "cloud_services": ["SOC 2", "ISO 27001", "GDPR", "FedRAMP", "NIS2"],
    "energy": ["NERC CIP", "IEC 62443", "NIS2"],
    "utilities": ["NERC CIP", "IEC 62443", "NIS2"],
    "telecommunications": ["NIS2", "GDPR", "ISO 27001"],
}
