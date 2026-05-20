"""
Tests for CompanyProfileAgent.

Claude's _run_with_web_search is mocked — no real API calls.

5 scenarios:
  1. No API key           → safe fallback, status "error"
  2. Full profile found   → all snapshot fields populated, status "completed"
  3. Partial profile      → some fields empty, status "partial"
  4. No data found        → empty snapshot, status "no_data"
  5. Invalid JSON         → safe fallback, status "error"
"""

import json
import unittest
from unittest.mock import patch

from agents.company_profile.agent import CompanyProfileAgent
from agents.company_profile.config import SNAPSHOT_FIELDS


def _make_response(**kwargs) -> str:
    snapshot = kwargs.get("snapshot", {field: "" for field in SNAPSHOT_FIELDS})
    doc = {
        "company": kwargs.get("company", "TestCo"),
        "domain": kwargs.get("domain", "testco.com"),
        "signal": "company_profile",
        "status": kwargs.get("status", "completed"),
        "snapshot": snapshot,
        "sources_checked": kwargs.get("sources_checked", []),
        "limitations": kwargs.get("limitations", []),
        "confidence": kwargs.get("confidence", "Medium"),
    }
    return json.dumps(doc)


class TestCompanyProfileAgent(unittest.TestCase):

    def setUp(self):
        self.agent = CompanyProfileAgent()
        self._key_patcher = patch(
            "agents.company_profile.agent.ANTHROPIC_API_KEY", "test-key"
        )
        self._key_patcher.start()

    def tearDown(self):
        self._key_patcher.stop()

    # ── Test 1: No API key ────────────────────────────────────────────────────

    def test_no_api_key_returns_fallback(self):
        with patch("agents.company_profile.agent.ANTHROPIC_API_KEY", ""):
            result = self.agent.run("TestCo", "testco.com")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["signal"], "company_profile")
        self.assertGreater(len(result["limitations"]), 0)
        for field in SNAPSHOT_FIELDS:
            self.assertEqual(result["snapshot"][field], "")

    # ── Test 2: Full profile ──────────────────────────────────────────────────

    def test_full_profile_populated(self):
        mock_json = _make_response(
            status="completed",
            confidence="High",
            snapshot={
                "what_they_do": "Provides cloud-based data analytics platform for enterprises.",
                "who_they_sell_to": "Mid-market and enterprise B2B customers in finance and retail.",
                "regions_scale": "~2,000 employees, $180M ARR, operates in US, EU, and APAC.",
                "business_model": "SaaS subscription with professional services add-on.",
                "key_acquisition": "Acquired DataStream Inc in 2023 to expand real-time pipeline capabilities.",
                "strategic_direction": "Expanding AI-native analytics features and growing APAC footprint.",
                "ai_posture": "Building AI products — launched AI co-pilot feature in Q1 2025.",
            },
            sources_checked=[
                {"url": "https://testco.com/about", "type": "company_website", "status": "fetched", "notes": ""},
                {"url": "https://testco.com/newsroom", "type": "newsroom", "status": "fetched", "notes": ""},
            ],
        )

        with patch.object(
            CompanyProfileAgent, "_run_with_web_search",
            return_value=(mock_json, []),
        ):
            result = self.agent.run("TestCo", "testco.com")

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["confidence"], "High")
        for field in SNAPSHOT_FIELDS:
            self.assertNotEqual(result["snapshot"][field], "")
        self.assertGreater(len(result["sources_checked"]), 0)

    # ── Test 3: Partial profile ───────────────────────────────────────────────

    def test_partial_profile(self):
        mock_json = _make_response(
            status="partial",
            confidence="Low",
            snapshot={
                "what_they_do": "B2B SaaS platform for logistics management.",
                "who_they_sell_to": "Logistics companies and 3PLs.",
                "regions_scale": "",
                "business_model": "",
                "key_acquisition": "",
                "strategic_direction": "",
                "ai_posture": "",
            },
            limitations=["Investor relations page not found; limited public information available."],
        )

        with patch.object(
            CompanyProfileAgent, "_run_with_web_search",
            return_value=(mock_json, []),
        ):
            result = self.agent.run("LogiCo", "logico.com")

        self.assertEqual(result["status"], "partial")
        self.assertNotEqual(result["snapshot"]["what_they_do"], "")
        self.assertEqual(result["snapshot"]["regions_scale"], "")
        self.assertGreater(len(result["limitations"]), 0)

    # ── Test 4: No data found ─────────────────────────────────────────────────

    def test_no_data_returns_empty_snapshot(self):
        mock_json = _make_response(
            status="no_data",
            confidence="Low",
            snapshot={field: "" for field in SNAPSHOT_FIELDS},
            limitations=["Company website returned no accessible content."],
        )

        with patch.object(
            CompanyProfileAgent, "_run_with_web_search",
            return_value=(mock_json, []),
        ):
            result = self.agent.run("StealthCo", "stealth.io")

        self.assertEqual(result["status"], "no_data")
        for field in SNAPSHOT_FIELDS:
            self.assertEqual(result["snapshot"][field], "")
        self.assertEqual(result["confidence"], "Low")

    # ── Test 5: Invalid JSON → safe fallback ──────────────────────────────────

    def test_invalid_json_returns_fallback(self):
        with patch.object(
            CompanyProfileAgent, "_run_with_web_search",
            return_value=("not valid json at all { broken", []),
        ):
            result = self.agent.run("TestCo", "testco.com")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["signal"], "company_profile")
        for field in SNAPSHOT_FIELDS:
            self.assertEqual(result["snapshot"][field], "")


if __name__ == "__main__":
    unittest.main()
