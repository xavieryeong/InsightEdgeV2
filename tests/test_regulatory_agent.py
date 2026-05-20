"""
Tests for RegulatoryImpactAgent.

Claude's _run_with_web_search is mocked — no real API calls.

8 scenarios:
  1. No API key configured         → safe fallback, status "error"
  2. Financial Singapore company   → MAS regulator evidence, regional score > 0
  3. Healthcare company            → HIPAA mapping, no central bank
  4. Manufacturing company         → MISRA mapping, no central bank
  5. Active fine evidence          → high score, direct source URL required
  6. Industry-only mapping         → total score <= INDUSTRY_ONLY_SCORE_CAP (3.0)
  7. No evidence found             → score <= 1, confidence Low
  8. Claude returns invalid JSON   → safe fallback, status "error"
"""

import json
import unittest
from unittest.mock import patch

from agents.regulatory.agent import RegulatoryImpactAgent
from agents.regulatory.config import INDUSTRY_ONLY_SCORE_CAP


def _blank_breakdown(**overrides) -> dict:
    base = {
        "active_fine_lawsuit": 0.0,
        "specific_regulation_applies": 0.0,
        "compliance_audit": 0.0,
        "regulated_industry": 0.0,
        "regional_regulator_relevance": 0.0,
        "general_regulatory_mention": 0.0,
        "total": 0.0,
    }
    base.update(overrides)
    base["total"] = sum(v for k, v in base.items() if k != "total")
    return base


def _make_response(**kwargs) -> str:
    """Build a valid mock Claude response JSON string."""
    evidence = kwargs.get("evidence", [])
    breakdown = kwargs.get("score_breakdown", _blank_breakdown())
    score = kwargs.get("sonar_relevance_score", breakdown.get("total", 0))
    detected = kwargs.get(
        "detected_categories",
        [k for k, v in breakdown.items() if k != "total" and v > 0],
    )

    doc = {
        "company": kwargs.get("company", "TestCo"),
        "domain": kwargs.get("domain", "testco.com"),
        "signal": "regulatory_impact",
        "status": kwargs.get("status", "completed"),
        "industry_detected": kwargs.get("industry_detected", "technology"),
        "country_detected": kwargs.get("country_detected", ""),
        "regulator_checked": kwargs.get("regulator_checked", ""),
        "regulator_website": kwargs.get("regulator_website", ""),
        "applicable_regulations": kwargs.get("applicable_regulations", []),
        "detected_categories": detected,
        "sonar_relevance_score": score,
        "score_breakdown": breakdown,
        "summary": kwargs.get("summary", "Test summary."),
        "sonar_relevance_reason": kwargs.get("sonar_relevance_reason", "Test reason."),
        "recommended_sales_angle": kwargs.get("recommended_sales_angle", "Test angle."),
        "confidence": kwargs.get("confidence", "Low"),
        "evidence": evidence,
        "limitations": kwargs.get("limitations", []),
        "sources_checked": kwargs.get("sources_checked", []),
    }
    return json.dumps(doc)


def _evidence_item(
    id_: str,
    type_: str,
    source_type: str,
    source_url: str = "",
    regulation: str = "",
    regulator: str = "",
    confidence: str = "Medium",
) -> dict:
    return {
        "id": id_,
        "type": type_,
        "value": regulation,
        "source_type": source_type,
        "source_url": source_url,
        "evidence_text": f"Evidence for {regulation or type_}",
        "regulation": regulation,
        "regulator": regulator,
        "country": "",
        "industry": "",
        "confidence": confidence,
        "counted_in_score": True,
    }


class TestRegulatoryAgent(unittest.TestCase):

    def setUp(self):
        self.agent = RegulatoryImpactAgent()
        # Patch API key so run() passes the early-return guard for all tests.
        # Test 1 overrides this patch to "" inside its own with block.
        self._key_patcher = patch("agents.regulatory.agent.ANTHROPIC_API_KEY", "test-key")
        self._key_patcher.start()

    def tearDown(self):
        self._key_patcher.stop()

    # ── Test 1: No API key ────────────────────────────────────────────────────

    def test_no_api_key_returns_fallback(self):
        # Override the setUp "test-key" patch with an empty key
        with patch("agents.regulatory.agent.ANTHROPIC_API_KEY", ""):
            result = self.agent.run("TestCo", "testco.com")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["signal"], "regulatory_impact")
        self.assertEqual(result["sonar_relevance_score"], 0)
        self.assertEqual(result["evidence"], [])
        self.assertGreater(len(result["limitations"]), 0)

    # ── Test 2: Financial Singapore company → MAS regulator ──────────────────

    def test_financial_singapore_searches_mas(self):
        mock_json = _make_response(
            company="DBS Bank",
            domain="dbs.com",
            status="completed",
            industry_detected="banking",
            country_detected="Singapore",
            regulator_checked="MAS",
            regulator_website="https://mas.gov.sg",
            score_breakdown=_blank_breakdown(
                specific_regulation_applies=2.0,
                regulated_industry=1.5,
                regional_regulator_relevance=1.0,
                general_regulatory_mention=0.5,
            ),
            confidence="High",
            applicable_regulations=[
                {
                    "name": "MAS Technology Risk Management Guidelines",
                    "relevance": "High",
                    "reason": "MAS TRM guidelines apply to all Singapore-licensed banks",
                    "evidence_ids": ["reg_001"],
                },
                {
                    "name": "PCI DSS 4.0",
                    "relevance": "High",
                    "reason": "Banking and payment processing requires PCI DSS compliance",
                    "evidence_ids": ["reg_002"],
                },
            ],
            evidence=[
                _evidence_item(
                    "reg_001", "regional_regulator_relevance",
                    "official_regulator_website",
                    source_url="https://mas.gov.sg/regulation/guidelines/technology-risk-management-guidelines",
                    regulation="MAS TRM",
                    regulator="MAS",
                    confidence="High",
                ),
                _evidence_item(
                    "reg_002", "specific_regulation_applies",
                    "industry_mapping",
                    regulation="PCI DSS 4.0",
                    regulator="PCI SSC",
                    confidence="Medium",
                ),
            ],
            sources_checked=[
                {
                    "url": "https://mas.gov.sg/regulation/guidelines/technology-risk-management-guidelines",
                    "source_type": "official_regulator_website",
                    "status": "fetched",
                    "notes": "MAS TRM Guidelines",
                }
            ],
        )

        with patch.object(
            RegulatoryImpactAgent, "_run_with_web_search",
            return_value=(mock_json, []),
        ):
            result = self.agent.run(
                "DBS Bank", "dbs.com",
                country="Singapore", industry="banking",
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["company"], "DBS Bank")
        self.assertEqual(result["regulator_checked"], "MAS")
        self.assertEqual(result["regulator_website"], "https://mas.gov.sg")
        self.assertEqual(result["country_detected"], "Singapore")
        self.assertIn("regional_regulator_relevance", result["detected_categories"])
        self.assertGreater(result["score_breakdown"]["regional_regulator_relevance"], 0)
        self.assertGreater(result["sonar_relevance_score"], 0)
        self.assertEqual(result["confidence"], "High")

        # At least one evidence item from official regulator website
        official_ev = [
            e for e in result["evidence"]
            if e["source_type"] == "official_regulator_website"
        ]
        self.assertGreater(len(official_ev), 0)

    # ── Test 3: Healthcare → HIPAA ────────────────────────────────────────────

    def test_healthcare_maps_to_hipaa(self):
        mock_json = _make_response(
            status="completed",
            industry_detected="healthcare",
            country_detected="United States",
            regulator_checked="",
            score_breakdown=_blank_breakdown(
                specific_regulation_applies=1.5,
                regulated_industry=1.0,
            ),
            confidence="Medium",
            applicable_regulations=[
                {
                    "name": "HIPAA",
                    "relevance": "High",
                    "reason": "Healthcare data handling requires HIPAA compliance",
                    "evidence_ids": ["reg_001"],
                }
            ],
            evidence=[
                _evidence_item(
                    "reg_001", "specific_regulation_applies",
                    "industry_mapping",
                    regulation="HIPAA",
                    regulator="HHS OCR",
                    confidence="Medium",
                ),
                _evidence_item(
                    "reg_002", "regulated_industry",
                    "industry_mapping",
                    regulation="",
                    confidence="Medium",
                ),
            ],
        )

        with patch.object(
            RegulatoryImpactAgent, "_run_with_web_search",
            return_value=(mock_json, []),
        ):
            result = self.agent.run(
                "HealthTech Inc", "healthtech.com", industry="healthcare"
            )

        reg_names = [r["name"] for r in result["applicable_regulations"]]
        self.assertIn("HIPAA", reg_names)
        self.assertEqual(result["industry_detected"], "healthcare")
        # No central bank lookup for healthcare
        self.assertEqual(result["regulator_checked"], "")

    # ── Test 4: Manufacturing → MISRA ─────────────────────────────────────────

    def test_manufacturing_maps_to_misra(self):
        mock_json = _make_response(
            status="completed",
            industry_detected="manufacturing",
            country_detected="Germany",
            regulator_checked="",
            score_breakdown=_blank_breakdown(
                specific_regulation_applies=1.5,
                regulated_industry=1.0,
            ),
            confidence="Medium",
            applicable_regulations=[
                {
                    "name": "MISRA C",
                    "relevance": "High",
                    "reason": "Safety-critical embedded software must follow MISRA coding standards",
                    "evidence_ids": ["reg_001"],
                },
                {
                    "name": "IEC 62443",
                    "relevance": "Medium",
                    "reason": "Industrial automation cybersecurity standard",
                    "evidence_ids": ["reg_002"],
                },
            ],
            evidence=[
                _evidence_item(
                    "reg_001", "specific_regulation_applies",
                    "industry_mapping",
                    regulation="MISRA C",
                    confidence="Medium",
                ),
                _evidence_item(
                    "reg_002", "specific_regulation_applies",
                    "industry_mapping",
                    regulation="IEC 62443",
                    confidence="Low",
                ),
            ],
        )

        with patch.object(
            RegulatoryImpactAgent, "_run_with_web_search",
            return_value=(mock_json, []),
        ):
            result = self.agent.run(
                "AutoParts GmbH", "autoparts.de", industry="manufacturing"
            )

        reg_names = [r["name"] for r in result["applicable_regulations"]]
        self.assertIn("MISRA C", reg_names)
        self.assertEqual(result["industry_detected"], "manufacturing")
        # No central bank lookup for manufacturing
        self.assertEqual(result["regulator_checked"], "")

    # ── Test 5: Active fine → high score with source URL ─────────────────────

    def test_active_fine_produces_high_score_with_url(self):
        mock_json = _make_response(
            status="completed",
            industry_detected="technology",
            country_detected="European Union",
            score_breakdown=_blank_breakdown(
                active_fine_lawsuit=3.0,
                specific_regulation_applies=2.0,
                regulated_industry=1.0,
            ),
            confidence="High",
            evidence=[
                _evidence_item(
                    "reg_001", "active_fine_lawsuit",
                    "public_news",
                    source_url="https://example.com/gdpr-fine-techcorp",
                    regulation="GDPR",
                    regulator="EU DPA",
                    confidence="High",
                ),
                _evidence_item(
                    "reg_002", "specific_regulation_applies",
                    "official_regulator_website",
                    source_url="https://edpb.europa.eu/example",
                    regulation="GDPR",
                    regulator="EDPB",
                    confidence="High",
                ),
            ],
        )

        with patch.object(
            RegulatoryImpactAgent, "_run_with_web_search",
            return_value=(mock_json, []),
        ):
            result = self.agent.run("TechCorp EU", "techcorp.eu")

        self.assertGreaterEqual(result["sonar_relevance_score"], 3.0)
        self.assertEqual(result["score_breakdown"]["active_fine_lawsuit"], 3.0)
        self.assertIn("active_fine_lawsuit", result["detected_categories"])
        self.assertEqual(result["confidence"], "High")

        # Fine evidence must have a real source URL
        fine_ev = [e for e in result["evidence"] if e["type"] == "active_fine_lawsuit"]
        self.assertGreater(len(fine_ev), 0)
        self.assertNotEqual(fine_ev[0]["source_url"], "")

    # ── Test 6: Industry-only mapping → score <= INDUSTRY_ONLY_SCORE_CAP ─────

    def test_industry_only_mapping_score_capped(self):
        # Claude correctly caps itself at 2.5 when only industry_mapping evidence
        mock_json = _make_response(
            status="partial",
            industry_detected="saas",
            country_detected="",
            score_breakdown=_blank_breakdown(
                specific_regulation_applies=1.5,
                regulated_industry=1.0,
            ),
            confidence="Low",
            evidence=[
                _evidence_item(
                    "reg_001", "regulated_industry",
                    "industry_mapping",
                    confidence="Low",
                ),
                _evidence_item(
                    "reg_002", "specific_regulation_applies",
                    "industry_mapping",
                    regulation="SOC 2",
                    confidence="Low",
                ),
            ],
            limitations=["Only industry mapping available; no external evidence found"],
        )

        with patch.object(
            RegulatoryImpactAgent, "_run_with_web_search",
            return_value=(mock_json, []),
        ):
            result = self.agent.run("SaaSCo", "saasco.io", industry="saas")

        self.assertLessEqual(result["sonar_relevance_score"], INDUSTRY_ONLY_SCORE_CAP)
        # All evidence sources are industry_mapping
        non_mapping = [
            e for e in result["evidence"]
            if e["source_type"] != "industry_mapping"
        ]
        self.assertEqual(len(non_mapping), 0)

    # ── Test 7: No evidence → score <= 1, Low confidence ─────────────────────

    def test_no_evidence_produces_zero_score(self):
        mock_json = _make_response(
            status="no_data",
            industry_detected="",
            country_detected="",
            score_breakdown=_blank_breakdown(),
            confidence="Low",
            evidence=[],
            limitations=["No regulatory information found for this company"],
        )

        with patch.object(
            RegulatoryImpactAgent, "_run_with_web_search",
            return_value=(mock_json, []),
        ):
            result = self.agent.run("Unknown Startup XYZ", "unknownxyz.io")

        self.assertLessEqual(result["sonar_relevance_score"], 1)
        self.assertEqual(len(result["evidence"]), 0)
        self.assertEqual(result["confidence"], "Low")
        self.assertGreater(len(result["limitations"]), 0)

    # ── Test 8: Invalid JSON → safe fallback ──────────────────────────────────

    def test_invalid_json_returns_fallback(self):
        with patch.object(
            RegulatoryImpactAgent, "_run_with_web_search",
            return_value=("this is not json { broken ][", []),
        ):
            result = self.agent.run("TestCo", "testco.com")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["signal"], "regulatory_impact")
        self.assertEqual(result["sonar_relevance_score"], 0)
        self.assertEqual(result["evidence"], [])
        self.assertGreater(len(result["limitations"]), 0)


if __name__ == "__main__":
    unittest.main()
