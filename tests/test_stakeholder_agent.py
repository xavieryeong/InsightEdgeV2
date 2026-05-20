from __future__ import annotations

"""
Tests for StakeholderIntelligenceAgent.

Claude's _run_with_web_search is mocked — no real API calls.

6 scenarios:
  1. No API key                         → safe fallback, status "error"
  2. Stakeholders found with personality → correct colours, display format "Red/Blue"
  3. Stakeholder found, no public content → personality Unknown/None, confidence Low
  4. No stakeholders found              → empty list, status "no_data"
  5. Invalid JSON                       → safe fallback, status "error"
  6. Same primary and secondary colour  → secondary normalised to "None"
"""

import json
import unittest
from unittest.mock import patch

from agents.stakeholder.agent import StakeholderIntelligenceAgent


def _make_response(**kwargs) -> str:
    doc = {
        "company": kwargs.get("company", "TestCo"),
        "domain": kwargs.get("domain", "testco.com"),
        "signal": "stakeholder_intelligence",
        "status": kwargs.get("status", "completed"),
        "stakeholders": kwargs.get("stakeholders", []),
        "sources_checked": kwargs.get("sources_checked", []),
        "limitations": kwargs.get("limitations", []),
        "confidence": kwargs.get("confidence", "Medium"),
    }
    return json.dumps(doc)


def _stakeholder(
    role: str,
    name: str,
    linkedin: str = "",
    confidence: str = "Medium",
    primary: str = "Red",
    secondary: str = "Blue",
    signals: list | None = None,
    reasoning: str = "Direct keynote style and outcome-focused language.",
    sources: list | None = None,
) -> dict:
    return {
        "role": role,
        "name": name,
        "linkedin_url": linkedin,
        "confidence": confidence,
        "personality_primary": primary,
        "personality_secondary": secondary,
        "personality_display": f"{primary}/{secondary}" if secondary != "None" else primary,
        "personality_signals": signals or ["Keynote at DevSummit 2024 — direct, metrics-driven"],
        "personality_reasoning": reasoning,
        "source_urls": sources or ["https://example.com/keynote"],
    }


class TestStakeholderAgent(unittest.TestCase):

    def setUp(self):
        self.agent = StakeholderIntelligenceAgent()
        self._key_patcher = patch(
            "agents.stakeholder.agent.ANTHROPIC_API_KEY", "test-key"
        )
        self._key_patcher.start()

    def tearDown(self):
        self._key_patcher.stop()

    # ── Test 1: No API key ────────────────────────────────────────────────────

    def test_no_api_key_returns_fallback(self):
        with patch("agents.stakeholder.agent.ANTHROPIC_API_KEY", ""):
            result = self.agent.run("TestCo", "testco.com")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["signal"], "stakeholder_intelligence")
        self.assertEqual(result["stakeholders"], [])
        self.assertGreater(len(result["limitations"]), 0)

    # ── Test 2: Stakeholders found with personality ───────────────────────────

    def test_stakeholders_with_personality_colours(self):
        mock_json = _make_response(
            status="completed",
            confidence="High",
            stakeholders=[
                _stakeholder(
                    "CTO", "Jane Smith",
                    linkedin="https://linkedin.com/in/janesmith",
                    confidence="High",
                    primary="Red", secondary="Blue",
                    signals=[
                        "Keynote at AWS re:Invent 2024 — direct, outcomes-focused tone",
                        "LinkedIn posts focus on shipping fast and metrics",
                    ],
                    reasoning="Predominantly direct and results-driven in all public appearances, with secondary analytical depth in technical blog posts.",
                    sources=["https://linkedin.com/in/janesmith", "https://aws.amazon.com/events/reinvent/2024/keynote"],
                ),
                _stakeholder(
                    "VP Engineering", "David Lee",
                    confidence="Medium",
                    primary="Blue", secondary="Green",
                    signals=["Technical blog posts are data-heavy with structured analysis"],
                    reasoning="Methodical and precise in writing; also emphasises team collaboration and steady delivery.",
                    sources=["https://testco.com/blog/david-lee"],
                ),
            ],
        )

        with patch.object(
            StakeholderIntelligenceAgent, "_run_with_web_search",
            return_value=(mock_json, []),
        ):
            result = self.agent.run("TestCo", "testco.com")

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["stakeholders"]), 2)

        cto = result["stakeholders"][0]
        self.assertEqual(cto["name"], "Jane Smith")
        self.assertEqual(cto["personality_primary"], "Red")
        self.assertEqual(cto["personality_secondary"], "Blue")
        self.assertEqual(cto["personality_display"], "Red/Blue")
        self.assertTrue(cto["linkedin_url"].startswith("https://"))
        self.assertGreater(len(cto["personality_signals"]), 0)

        vp = result["stakeholders"][1]
        self.assertEqual(vp["personality_display"], "Blue/Green")

    # ── Test 3: No public content → Unknown personality ───────────────────────

    def test_no_personality_signals_returns_unknown(self):
        mock_json = _make_response(
            status="partial",
            confidence="Low",
            stakeholders=[
                {
                    "role": "CTO",
                    "name": "Alex Kim",
                    "linkedin_url": "",
                    "confidence": "Low",
                    "personality_primary": "Unknown",
                    "personality_secondary": "None",
                    "personality_display": "Unknown",
                    "personality_signals": [],
                    "personality_reasoning": "No public content found for personality inference.",
                    "source_urls": ["https://testco.com/team"],
                }
            ],
            limitations=["No LinkedIn activity or public speeches found for Alex Kim."],
        )

        with patch.object(
            StakeholderIntelligenceAgent, "_run_with_web_search",
            return_value=(mock_json, []),
        ):
            result = self.agent.run("TestCo", "testco.com")

        self.assertEqual(len(result["stakeholders"]), 1)
        person = result["stakeholders"][0]
        self.assertEqual(person["personality_primary"], "Unknown")
        self.assertEqual(person["personality_secondary"], "None")
        self.assertEqual(person["personality_display"], "Unknown")
        self.assertEqual(person["confidence"], "Low")
        self.assertEqual(person["personality_signals"], [])

    # ── Test 4: No stakeholders found ────────────────────────────────────────

    def test_no_stakeholders_found(self):
        mock_json = _make_response(
            status="no_data",
            confidence="Low",
            stakeholders=[],
            limitations=["Could not identify named technical leadership from public sources."],
        )

        with patch.object(
            StakeholderIntelligenceAgent, "_run_with_web_search",
            return_value=(mock_json, []),
        ):
            result = self.agent.run("StealthCo", "stealth.io")

        self.assertEqual(result["status"], "no_data")
        self.assertEqual(result["stakeholders"], [])
        self.assertEqual(result["confidence"], "Low")

    # ── Test 5: Invalid JSON → safe fallback ──────────────────────────────────

    def test_invalid_json_returns_fallback(self):
        with patch.object(
            StakeholderIntelligenceAgent, "_run_with_web_search",
            return_value=("not valid json { broken ][", []),
        ):
            result = self.agent.run("TestCo", "testco.com")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["signal"], "stakeholder_intelligence")
        self.assertEqual(result["stakeholders"], [])

    # ── Test 6: Same primary and secondary → secondary normalised to None ─────

    def test_same_primary_secondary_normalised(self):
        mock_json = _make_response(
            status="partial",
            stakeholders=[
                {
                    "role": "CTO",
                    "name": "Sam Wong",
                    "linkedin_url": "",
                    "confidence": "Medium",
                    "personality_primary": "Red",
                    "personality_secondary": "Red",   # same as primary — invalid
                    "personality_display": "Red/Red",
                    "personality_signals": ["Strong results focus in all posts"],
                    "personality_reasoning": "Consistently results-driven.",
                    "source_urls": ["https://example.com"],
                }
            ],
        )

        with patch.object(
            StakeholderIntelligenceAgent, "_run_with_web_search",
            return_value=(mock_json, []),
        ):
            result = self.agent.run("TestCo", "testco.com")

        person = result["stakeholders"][0]
        self.assertEqual(person["personality_secondary"], "None")
        self.assertEqual(person["personality_display"], "Red")


if __name__ == "__main__":
    unittest.main()
