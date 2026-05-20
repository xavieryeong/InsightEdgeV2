"""
Tests for CompanyPositionAgent.

Focus: Python scoring and classification logic only.
Claude's ask_claude() is mocked — tests do not make real API calls.

5 scenarios:
  1. AI Leader  — AI news + AI hiring + modern cloud/CI/CD stack
  2. Skeptic    — responsible AI / governance signals + security-only hiring
  3. Laggard    — weak/empty signals across all dimensions
  4. High score but dominant skeptic flags → Skeptic (tie-breaker)
  5. Missing inputs (all None) → Laggard, Low confidence, score 0
"""

import json
import unittest
from unittest.mock import patch

from agents.company_position.agent import CompanyPositionAgent

_MOCK_INTERP = json.dumps({
    "summary": "Mock summary.",
    "classification_reason": "Mock reason.",
    "recommended_sales_angle": "Mock sales angle.",
    "limitations": [],
})


class TestCompanyPositionAgent(unittest.TestCase):

    def setUp(self):
        self.agent = CompanyPositionAgent()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _run(self, **kwargs):
        with patch.object(CompanyPositionAgent, "ask_claude", return_value=_MOCK_INTERP):
            return self.agent.run(**kwargs)

    # ── Test 1: AI Leader ─────────────────────────────────────────────────────

    def test_ai_leader(self):
        result = self._run(
            company="TechCorp",
            tech_stack_result={
                "status": "completed",
                "sonar_relevance_score": 7.5,
                "score_breakdown": {
                    "cicd_tools": {"GitHub Actions": 1.0, "Jenkins": 1.0},
                    "cloud_devops": {"AWS": 1.0, "Kubernetes": 1.0},
                    "languages": {"Java": 1.5, "TypeScript": 1.5},
                    "security_tooling": {},
                    "evidence_confidence": 0.5,
                    "total": 7.5,
                },
            },
            hiring_result={
                "status": "completed",
                "confidence": "High",
                "detected_categories": [
                    "devsecops", "devops", "cloud", "software_engineer",
                ],
            },
            news_result={
                "status": "completed",
                "confidence": "High",
                "detected_categories": ["cloud_ai_initiative", "product_launch"],
                "evidence": [
                    {
                        "title": "TechCorp launches new AI platform",
                        "snippet": (
                            "TechCorp announces a major AI initiative for "
                            "cloud transformation and innovation."
                        ),
                        "confidence": "High",
                        "counted_in_score": True,
                        "url": "",
                    }
                ],
            },
        )

        self.assertEqual(result["signal"], "company_position_focus")
        self.assertEqual(result["position_label"], "AI Leader")
        self.assertGreaterEqual(result["classification_score"], LEADER_THRESHOLD)
        self.assertEqual(result["dimension_scores"]["ai_innovation_news"], 2)
        self.assertEqual(result["dimension_scores"]["hiring_signals"], 2)
        self.assertEqual(result["dimension_scores"]["tech_stack_maturity"], 2)
        self.assertGreaterEqual(result["dimension_scores"]["engineering_visibility"], 1)
        self.assertEqual(result["confidence"], "High")
        self.assertIsInstance(result["evidence"], list)
        self.assertGreater(len(result["evidence"]), 0)

    # ── Test 2: Skeptic ───────────────────────────────────────────────────────

    def test_skeptic(self):
        result = self._run(
            company="BankCo",
            hiring_result={
                "status": "completed",
                "confidence": "Medium",
                "detected_categories": ["security"],
            },
            news_result={
                "status": "completed",
                "confidence": "Medium",
                "detected_categories": ["compliance_regulatory", "security_incident"],
                "evidence": [
                    {
                        "title": "BankCo implements responsible AI governance framework",
                        "snippet": (
                            "BankCo adopts responsible AI policies amid regulatory "
                            "caution and privacy concerns."
                        ),
                        "confidence": "Medium",
                        "counted_in_score": True,
                        "url": "",
                    }
                ],
            },
        )

        self.assertEqual(result["position_label"], "Skeptic")
        self.assertGreater(len(result["skeptic_flags"]), 0)
        self.assertIn("responsible ai", result["skeptic_flags"])

    # ── Test 3: Laggard ───────────────────────────────────────────────────────

    def test_laggard(self):
        result = self._run(
            company="LegacyCo",
            tech_stack_result={
                "status": "no_data",
                "sonar_relevance_score": 0,
                "score_breakdown": {},
            },
            hiring_result={
                "status": "no_data",
                "detected_categories": [],
            },
            news_result={
                "status": "no_data",
                "detected_categories": [],
                "evidence": [],
            },
        )

        self.assertEqual(result["position_label"], "Laggard")
        self.assertEqual(result["classification_score"], 0)
        self.assertEqual(result["confidence"], "Low")
        for score in result["dimension_scores"].values():
            self.assertEqual(score, 0)

    # ── Test 4: High score but dominant skeptic flags → Skeptic ──────────────

    def test_high_score_skeptic_override(self):
        result = self._run(
            company="FinanceCo",
            tech_stack_result={
                "status": "completed",
                "sonar_relevance_score": 7.0,
                "score_breakdown": {
                    "cicd_tools": {"GitHub Actions": 1.0},
                    "cloud_devops": {"AWS": 1.0, "Azure": 1.0},
                    "languages": {"Java": 1.5, "Python": 1.5},
                    "security_tooling": {},
                    "evidence_confidence": 0.5,
                    "total": 7.0,
                },
            },
            hiring_result={
                "status": "completed",
                "confidence": "High",
                "detected_categories": ["devops", "cloud", "security"],
            },
            news_result={
                "status": "completed",
                "confidence": "Medium",
                "detected_categories": ["cloud_ai_initiative", "compliance_regulatory"],
                "evidence": [
                    {
                        "title": "FinanceCo adopts responsible AI governance",
                        "snippet": (
                            "FinanceCo emphasizes AI governance, responsible AI "
                            "framework, and regulatory caution across all AI projects."
                        ),
                        "confidence": "Medium",
                        "counted_in_score": True,
                        "url": "",
                    }
                ],
            },
        )

        # High tech score should be overridden by dominant skeptic flags
        self.assertEqual(result["position_label"], "Skeptic")
        self.assertGreaterEqual(len(result["skeptic_flags"]), SKEPTIC_DOMINANT_COUNT)

    # ── Test 5: Missing inputs ────────────────────────────────────────────────

    def test_missing_inputs(self):
        result = self._run(company="UnknownCo")

        self.assertEqual(result["position_label"], "Laggard")
        self.assertEqual(result["classification_score"], 0)
        self.assertEqual(result["confidence"], "Low")
        self.assertEqual(result["skeptic_flags"], [])
        self.assertEqual(result["evidence"], [])
        for score in result["dimension_scores"].values():
            self.assertEqual(score, 0)


# Import threshold constant for assertion readability
from agents.company_position.config import LEADER_THRESHOLD, SKEPTIC_DOMINANT_COUNT

if __name__ == "__main__":
    unittest.main()
