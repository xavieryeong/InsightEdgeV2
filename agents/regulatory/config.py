from __future__ import annotations

# ── Score category caps ──────────────────────────────────────────────────────

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

# ── Qualifying signal keywords ───────────────────────────────────────────────
# A finding must contain at least one of these to be Sonar-relevant.
# Add keywords here to widen the net; remove to tighten it.

QUALIFYING_SIGNAL_KEYWORDS: list[str] = [
    "application security",
    "secure software development",
    "secure SDLC",
    "SDLC",
    "software security",
    "code quality",
    "static analysis",
    "SAST",
    "DAST",
    "vulnerability management",
    "vulnerability assessment",
    "penetration testing",
    "cybersecurity",
    "cyber resilience",
    "information security",
    "technology risk",
    "IT risk",
    "IT security",
    "secure coding",
    "software vulnerability",
    "patch management",
    "security testing",
    "DevSecOps",
    "security audit",
    "ISO 27001",
    "SOC 2",
    "PCI DSS",
    "MISRA",
    "IEC 62443",
    "FedRAMP",
    "CMMC",
    "NIS2",
    "DORA",
    "operational resilience",
    "cyber incident",
    "data breach",
    "enforcement action",
    "regulatory fine",
    "security certification",
]

# ── Ignore signal keywords ───────────────────────────────────────────────────
# Any finding that is ONLY about these topics (no qualifying keyword present)
# should be excluded — it is not relevant to Sonar.
# Add keywords here to tighten the filter.

REGULATOR_IGNORE_SIGNALS: list[str] = [
    "anti-money laundering",
    "AML",
    "KYC",
    "know your customer",
    "capital adequacy",
    "capital requirement",
    "Basel",
    "liquidity ratio",
    "reserve requirement",
    "consumer protection",
    "financial inclusion",
    "interest rate",
    "foreign exchange",
    "exchange rate",
    "monetary policy",
    "inflation",
    "credit rating",
    "loan classification",
    "non-performing loan",
    "NPL",
    "dividend policy",
    "merger approval",
    "acquisition approval",
    "employment law",
    "labour regulation",
    "HR compliance",
    "tax compliance",
    "VAT",
    "GST",
    "transfer pricing",
    "securities law",
    "insider trading",
    "market manipulation",
    "disclosure requirement",
    "corporate governance",  # alone is too generic — only relevant if tied to IT/security
]

# ── Country → Regulator map ──────────────────────────────────────────────────
# Each entry defines:
#   short_name     : regulator abbreviation shown in UI
#   full_name      : full official name
#   website        : base URL
#   target_pages   : specific pages/sections to search first (most relevant to Sonar)
#   look_for       : what signal types to look for on this regulator's site
#
# To add a new country: copy an existing entry and fill in the fields.
# To add a new page for an existing regulator: append to target_pages.
# To refine what Claude looks for: edit look_for.

COUNTRY_REGULATOR_MAP: dict[str, dict] = {
    "singapore": {
        "short_name": "MAS",
        "full_name": "Monetary Authority of Singapore",
        "website": "https://mas.gov.sg",
        "target_pages": [
            "https://mas.gov.sg/regulation/technology-risk",
            "https://mas.gov.sg/regulation/notices",
            "https://mas.gov.sg/regulation/guidelines",
        ],
        "look_for": [
            "Technology Risk Management (TRM) Guidelines",
            "cybersecurity notices and circulars",
            "IT audit and control requirements",
            "secure software development lifecycle requirements",
            "application security mandates",
            "enforcement actions or fines related to IT/cyber failures",
            "operational resilience requirements",
        ],
    },
    "indonesia": {
        "short_name": "OJK",
        "full_name": "Otoritas Jasa Keuangan",
        "website": "https://ojk.go.id",
        "target_pages": [
            "https://ojk.go.id/id/regulasi/Pages/Penyelenggaraan-Teknologi-Informasi-Oleh-Bank-Umum.aspx",
            "https://ojk.go.id/id/regulasi/Pages/Ketahanan-dan-Keamanan-Siber-Bagi-Bank-Umum.aspx",
            "https://ojk.go.id/id/berita-dan-kegiatan/siaran-pers",
        ],
        "look_for": [
            "POJK 11/2022 IT risk management for commercial banks",
            "OJK cyber resilience and security regulation",
            "application security and vulnerability management requirements",
            "IT audit requirements for financial institutions",
            "enforcement actions or sanctions related to IT/cyber failures",
            "secure software development requirements",
        ],
    },
    "malaysia": {
        "short_name": "BNM",
        "full_name": "Bank Negara Malaysia",
        "website": "https://bnm.gov.my",
        "target_pages": [
            "https://www.bnm.gov.my/documents/20124/963937/Risk+Management+in+Technology.pdf",
            "https://www.bnm.gov.my/regulatory-frameworks",
        ],
        "look_for": [
            "Risk Management in Technology (RMiT) policy document",
            "cybersecurity control requirements",
            "secure software development and application security",
            "IT audit and vulnerability assessment requirements",
            "enforcement actions related to technology risk failures",
            "operational resilience and business continuity for IT",
        ],
    },
    "philippines": {
        "short_name": "BSP",
        "full_name": "Bangko Sentral ng Pilipinas",
        "website": "https://bsp.gov.ph",
        "target_pages": [
            "https://www.bsp.gov.ph/Regulations/Issuances/2022/1140.pdf",
            "https://www.bsp.gov.ph/Regulations/Issuances/2017/c982.pdf",
            "https://www.bsp.gov.ph/Regulations/Regulations.aspx",
        ],
        "look_for": [
            "BSP Circular 1140 Technology Risk Management",
            "BSP Circular 982 Information Security Management",
            "cybersecurity framework requirements",
            "application security and vulnerability management",
            "IT audit and penetration testing requirements",
            "enforcement actions related to cyber or IT failures",
            "secure SDLC and software security requirements",
        ],
    },
    "thailand": {
        "short_name": "BOT",
        "full_name": "Bank of Thailand",
        "website": "https://bot.or.th",
        "target_pages": [
            "https://www.bot.or.th/en/financial-innovation/digital-finance/cyber-resilience.html",
            "https://www.bot.or.th/content/dam/bot/fipcs/documents/FPG/2561/EngPDF/25610093.pdf",
        ],
        "look_for": [
            "BOT Technology Risk Management Guidelines",
            "cybersecurity and cyber resilience requirements",
            "IT audit and application security requirements",
            "secure software development requirements",
            "enforcement actions for technology or cyber failures",
        ],
    },
    "vietnam": {
        "short_name": "SBV + MIC",
        "full_name": "State Bank of Vietnam / Ministry of Information and Communications",
        "website": "https://sbv.gov.vn",
        "target_pages": [
            "https://vanbanphapluat.co/circular-09-2020-tt-nhnn-prescribing-the-security-of-information-systems-in-banking-operations",
            "https://thuvienphapluat.vn/van-ban/EN/Cong-nghe-thong-tin/Law-24-2018-QH14-Cybersecurity/388829/tieng-anh.aspx",
            "https://english.luatvietnam.vn/thong-tin/circular-12-2022-tt-btttt-amend-85-2016-nd-cp-ensuring-the-security-of-information-systems-by-levels-228347-d1.html",
        ],
        "look_for": [
            "SBV Circular 09/2020 on information security in banking",
            "Vietnam Cybersecurity Law No. 24/2018/QH14 requirements",
            "MIC Circular 12/2022/TT-BTTTT on information system security levels",
            "Decree 13/2023/ND-CP personal data protection (if code-related breach)",
            "application security and vulnerability assessment requirements",
            "enforcement actions related to cyber or software failures",
        ],
    },
    "hong kong": {
        "short_name": "HKMA",
        "full_name": "Hong Kong Monetary Authority",
        "website": "https://hkma.gov.hk",
        "target_pages": [
            "https://www.hkma.gov.hk/eng/regulatory-resources/regulatory-guides/guidelines-and-circulars/",
            "https://www.hkma.gov.hk/eng/key-functions/banking-stability/cybersecurity/",
        ],
        "look_for": [
            "Cybersecurity Fortification Initiative (CFI)",
            "technology risk management circulars",
            "application security and vulnerability management",
            "IT audit requirements for authorized institutions",
            "enforcement actions for cyber or technology failures",
        ],
    },
    "india": {
        "short_name": "RBI",
        "full_name": "Reserve Bank of India",
        "website": "https://rbi.org.in",
        "target_pages": [
            "https://rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx",
            "https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx",
        ],
        "look_for": [
            "RBI Guidelines on Information Security, Electronic Banking and Cyber Frauds",
            "cybersecurity framework for banks and NBFCs",
            "application security and software vulnerability requirements",
            "IT audit and VAPT (vulnerability assessment and penetration testing)",
            "enforcement actions related to IT or cyber failures",
        ],
    },
    "australia": {
        "short_name": "APRA",
        "full_name": "Australian Prudential Regulation Authority",
        "website": "https://apra.gov.au",
        "target_pages": [
            "https://www.apra.gov.au/information-security",
            "https://www.apra.gov.au/prudential-standards-and-guidance",
        ],
        "look_for": [
            "CPS 234 Information Security standard",
            "application security and vulnerability management requirements",
            "IT audit and penetration testing requirements",
            "secure software development lifecycle",
            "enforcement actions for information security failures",
        ],
    },
    "united kingdom": {
        "short_name": "FCA",
        "full_name": "Financial Conduct Authority",
        "website": "https://fca.org.uk",
        "target_pages": [
            "https://www.fca.org.uk/firms/operational-resilience",
            "https://www.fca.org.uk/firms/cyber-security",
        ],
        "look_for": [
            "operational resilience requirements (PS21/3)",
            "cybersecurity requirements and guidance",
            "application security and vulnerability management",
            "IT audit and DORA-equivalent requirements",
            "enforcement actions for technology or cyber failures",
        ],
    },
    "uk": {
        "short_name": "FCA",
        "full_name": "Financial Conduct Authority",
        "website": "https://fca.org.uk",
        "target_pages": [
            "https://www.fca.org.uk/firms/operational-resilience",
            "https://www.fca.org.uk/firms/cyber-security",
        ],
        "look_for": [
            "operational resilience requirements (PS21/3)",
            "cybersecurity requirements and guidance",
            "application security and vulnerability management",
            "enforcement actions for technology or cyber failures",
        ],
    },
    "european union": {
        "short_name": "EBA + ENISA",
        "full_name": "European Banking Authority / EU Agency for Cybersecurity",
        "website": "https://eba.europa.eu",
        "target_pages": [
            "https://www.eba.europa.eu/regulation-and-policy/operational-resilience",
            "https://www.enisa.europa.eu/topics/cybersecurity-policy/nis-directive-new",
        ],
        "look_for": [
            "DORA (Digital Operational Resilience Act) requirements",
            "NIS2 Directive cybersecurity requirements",
            "EBA Guidelines on ICT and security risk management",
            "application security and vulnerability management",
            "enforcement actions for ICT or cyber failures",
        ],
    },
    "eu": {
        "short_name": "EBA + ENISA",
        "full_name": "European Banking Authority / EU Agency for Cybersecurity",
        "website": "https://eba.europa.eu",
        "target_pages": [
            "https://www.eba.europa.eu/regulation-and-policy/operational-resilience",
            "https://www.enisa.europa.eu/topics/cybersecurity-policy/nis-directive-new",
        ],
        "look_for": [
            "DORA (Digital Operational Resilience Act) requirements",
            "NIS2 Directive cybersecurity requirements",
            "EBA Guidelines on ICT and security risk management",
            "application security and vulnerability management",
        ],
    },
    "united states": {
        "short_name": "FFIEC",
        "full_name": "Federal Financial Institutions Examination Council",
        "website": "https://ffiec.gov",
        "target_pages": [
            "https://www.ffiec.gov/cyberassessmenttool.htm",
            "https://csrc.nist.gov/publications/sp800",
        ],
        "look_for": [
            "FFIEC Cybersecurity Assessment Tool requirements",
            "NIST SP 800-53 / SP 800-171 application security controls",
            "FedRAMP / CMMC requirements if government-related",
            "application security and vulnerability management mandates",
            "enforcement actions for cybersecurity failures",
        ],
    },
    "us": {
        "short_name": "FFIEC",
        "full_name": "Federal Financial Institutions Examination Council",
        "website": "https://ffiec.gov",
        "target_pages": [
            "https://www.ffiec.gov/cyberassessmenttool.htm",
            "https://csrc.nist.gov/publications/sp800",
        ],
        "look_for": [
            "FFIEC Cybersecurity Assessment Tool requirements",
            "NIST SP 800-53 application security controls",
            "FedRAMP / CMMC requirements",
            "enforcement actions for cybersecurity failures",
        ],
    },
    "usa": {
        "short_name": "FFIEC",
        "full_name": "Federal Financial Institutions Examination Council",
        "website": "https://ffiec.gov",
        "target_pages": [
            "https://www.ffiec.gov/cyberassessmenttool.htm",
        ],
        "look_for": [
            "FFIEC Cybersecurity Assessment Tool requirements",
            "NIST SP 800-53 application security controls",
            "enforcement actions for cybersecurity failures",
        ],
    },
}

# ── Industries that trigger financial regulator lookup ───────────────────────

FINANCIAL_INDUSTRIES = frozenset({
    "financial_services", "banking", "fintech", "insurance",
    "payments", "retail_payments", "lending", "card_issuing",
    "acquiring", "merchant_services", "investment_banking",
    "wealth_management", "brokerage", "neobank",
})

# ── Industry → applicable regulatory frameworks ──────────────────────────────

INDUSTRY_REGULATION_MAP: dict[str, list[str]] = {
    "financial_services": ["PCI DSS 4.0", "ISO 27001", "SOC 2", "DORA"],
    "banking":            ["PCI DSS 4.0", "ISO 27001", "DORA", "NIS2"],
    "fintech":            ["PCI DSS 4.0", "ISO 27001", "SOC 2", "DORA"],
    "payments":           ["PCI DSS 4.0", "ISO 27001"],
    "retail_payments":    ["PCI DSS 4.0", "ISO 27001"],
    "insurance":          ["SOC 2", "ISO 27001", "DORA"],
    "healthcare":         ["HIPAA", "HITRUST", "ISO 27001", "SOC 2"],
    "medical_devices":    ["HIPAA", "IEC 62304", "ISO 13485", "ISO 27001"],
    "manufacturing":      ["MISRA", "IEC 62443", "ISO 27001"],
    "automotive":         ["MISRA C/C++", "ISO 26262", "IEC 62443", "ISO 27001"],
    "aerospace":          ["DO-178C", "IEC 62443", "ISO 27001"],
    "public_sector":      ["FedRAMP", "CMMC", "NIST SP 800-53"],
    "government":         ["FedRAMP", "CMMC", "NIST SP 800-53"],
    "defense":            ["CMMC", "NIST SP 800-171", "ITAR"],
    "saas":               ["SOC 2", "ISO 27001", "NIS2"],
    "technology":         ["SOC 2", "ISO 27001", "NIS2"],
    "cloud_services":     ["SOC 2", "ISO 27001", "FedRAMP", "NIS2"],
    "energy":             ["NERC CIP", "IEC 62443", "NIS2"],
    "utilities":          ["NERC CIP", "IEC 62443", "NIS2"],
    "telecommunications": ["NIS2", "ISO 27001"],
}
