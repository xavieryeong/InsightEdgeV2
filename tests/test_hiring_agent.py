"""
Tests for the Velocity HiringPatternAgent (Claude-native design).

Run with:  python -m pytest tests/test_hiring_agent.py -v
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from agents.hiring.agent import HiringPatternAgent
from agents.hiring.models import validate_evidence_item, validate_score_breakdown
from agents.hiring.config import SCORE_CAPS, VALID_SCORE_CATEGORIES, TOTAL_SCORE_CAP


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_agent_with_mock_client() -> tuple[HiringPatternAgent, MagicMock]:
    agent = HiringPatternAgent.__new__(HiringPatternAgent)
    agent.client = MagicMock()
    agent.model = "claude-test-model"
    return agent, agent.client


def _valid_response(company: str = "Acme Corp", domain: str = "acmecorp.com") -> str:
    return json.dumps({
        "company": company,
        "domain": domain,
        "signal": "hiring_patterns",
        "status": "completed",
        "detected_categories": ["devsecops_appsec", "devops_platform"],
        "sonar_relevance_score": 6.5,
        "score_breakdown": {
            "devsecops_appsec": 3.0,
            "devops_platform": 2.5,
            "software_engineering_growth": 0.0,
            "cloud_infrastructure": 0.5,
            "security_compliance": 0.0,
            "recency_bonus": 0.5,
            "total": 6.5,
        },
        "summary": "Acme Corp is hiring DevSecOps and platform engineers.",
        "sonar_relevance_reason": "Active AppSec and DevOps investment suggests Sonar need.",
        "confidence": "High",
        "evidence": [
            {
                "id": "hire_001",
                "type": "devsecops_appsec",
                "value": "Application Security Engineer",
                "source_type": "ats_platform",
                "source_url": "https://boards.greenhouse.io/acmecorp",
                "title": "Application Security Engineer — Acme Corp",
                "evidence_text": "Role requires SAST, code scanning, and secure SDLC experience.",
                "company_match": "High",
                "confidence": "High",
                "counted_in_score": True,
            },
            {
                "id": "hire_002",
                "type": "devops_platform",
                "value": "Platform Engineer",
                "source_type": "ats_platform",
                "source_url": "https://boards.greenhouse.io/acmecorp",
                "title": "Platform Engineer — Acme Corp",
                "evidence_text": "CI/CD pipeline ownership, Kubernetes, GitHub Actions.",
                "company_match": "High",
                "confidence": "High",
                "counted_in_score": True,
            },
        ],
        "limitations": [],
        "sources_checked": [
            {"url": "https://boards.greenhouse.io/acmecorp", "source_type": "ats_platform",
             "status": "fetched", "notes": ""},
        ],
    })


def _mock_end_turn_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.type = "text"
    content_block.text = text
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = [content_block]
    return resp


# ── Output structure ──────────────────────────────────────────────────────────

class TestOutputStructure(unittest.TestCase):

    @patch("agents.hiring.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_all_required_keys_present(self):
        agent, mock_client = _make_agent_with_mock_client()
        mock_client.messages.create.return_value = _mock_end_turn_response(_valid_response())

        result = agent.run("Acme Corp", "acmecorp.com")

        required = [
            "company", "domain", "signal", "status", "detected_categories",
            "sonar_relevance_score", "score_breakdown", "summary",
            "sonar_relevance_reason", "confidence", "evidence",
            "limitations", "sources_checked",
        ]
        for key in required:
            self.assertIn(key, result, f"Missing key: {key}")

    @patch("agents.hiring.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_score_breakdown_has_all_categories(self):
        agent, mock_client = _make_agent_with_mock_client()
        mock_client.messages.create.return_value = _mock_end_turn_response(_valid_response())

        result = agent.run("Acme Corp", "acmecorp.com")

        for cat in VALID_SCORE_CATEGORIES:
            self.assertIn(cat, result["score_breakdown"], f"Missing breakdown key: {cat}")
        self.assertIn("total", result["score_breakdown"])

    @patch("agents.hiring.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_company_and_domain_set_correctly(self):
        agent, mock_client = _make_agent_with_mock_client()
        mock_client.messages.create.return_value = _mock_end_turn_response(_valid_response())

        result = agent.run("Acme Corp", "acmecorp.com", country="US", industry="Software")
        self.assertEqual(result["company"], "Acme Corp")
        self.assertEqual(result["domain"], "acmecorp.com")


# ── Score enforcement ─────────────────────────────────────────────────────────

class TestScoreEnforcement(unittest.TestCase):

    @patch("agents.hiring.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_score_capped_per_category(self):
        inflated = json.loads(_valid_response())
        inflated["score_breakdown"]["devsecops_appsec"] = 99.0
        inflated["score_breakdown"]["devops_platform"] = 99.0
        inflated["score_breakdown"]["total"] = 198.0

        agent, mock_client = _make_agent_with_mock_client()
        mock_client.messages.create.return_value = _mock_end_turn_response(json.dumps(inflated))

        result = agent.run("Acme Corp", "acmecorp.com")

        for cat, cap in SCORE_CAPS.items():
            self.assertLessEqual(result["score_breakdown"][cat], cap,
                                 f"Category {cat} exceeded its cap")
        self.assertLessEqual(result["sonar_relevance_score"], TOTAL_SCORE_CAP)

    @patch("agents.hiring.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_no_counted_evidence_forces_zero_score(self):
        no_evidence = json.loads(_valid_response())
        for ev in no_evidence["evidence"]:
            ev["counted_in_score"] = False
        no_evidence["score_breakdown"]["devsecops_appsec"] = 3.0
        no_evidence["score_breakdown"]["total"] = 3.0

        agent, mock_client = _make_agent_with_mock_client()
        mock_client.messages.create.return_value = _mock_end_turn_response(json.dumps(no_evidence))

        result = agent.run("Acme Corp", "acmecorp.com")

        self.assertEqual(result["sonar_relevance_score"], 0)
        self.assertEqual(result["score_breakdown"]["total"], 0)
        self.assertEqual(result["status"], "no_data")

    @patch("agents.hiring.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_total_score_matches_sum(self):
        agent, mock_client = _make_agent_with_mock_client()
        mock_client.messages.create.return_value = _mock_end_turn_response(_valid_response())

        result = agent.run("Acme Corp", "acmecorp.com")

        computed = sum(result["score_breakdown"][c] for c in VALID_SCORE_CATEGORIES)
        self.assertAlmostEqual(result["score_breakdown"]["total"], min(computed, TOTAL_SCORE_CAP), places=5)


# ── Evidence validation ───────────────────────────────────────────────────────

class TestEvidenceValidation(unittest.TestCase):

    def test_invalid_type_normalised(self):
        item = {"type": "random_garbage", "counted_in_score": True, "source_url": "https://x.com", "confidence": "High"}
        result = validate_evidence_item(item, 0)
        self.assertEqual(result["type"], "software_engineering_growth")

    def test_invalid_confidence_normalised(self):
        item = {"confidence": "SuperHigh", "counted_in_score": True}
        result = validate_evidence_item(item, 0)
        self.assertEqual(result["confidence"], "Low")

    def test_low_confidence_no_url_not_counted(self):
        item = {"confidence": "Low", "source_url": "", "counted_in_score": True}
        result = validate_evidence_item(item, 0)
        self.assertFalse(result["counted_in_score"])

    def test_string_true_counted_in_score(self):
        item = {"counted_in_score": "true", "source_url": "https://x.com", "confidence": "High"}
        result = validate_evidence_item(item, 0)
        self.assertTrue(result["counted_in_score"])

    def test_defaults_populated(self):
        result = validate_evidence_item({}, 2)
        self.assertEqual(result["id"], "hire_003")
        self.assertEqual(result["company_match"], "Low")
        self.assertEqual(result["source_type"], "claude_web_search_result")

    def test_invalid_source_type_normalised(self):
        item = {"source_type": "made_up_type", "confidence": "High", "source_url": "https://x.com"}
        result = validate_evidence_item(item, 0)
        self.assertEqual(result["source_type"], "claude_web_search_result")


# ── Score breakdown validation ────────────────────────────────────────────────

class TestScoreBreakdownValidation(unittest.TestCase):

    def test_clamped_to_caps(self):
        breakdown = {cat: 99.0 for cat in VALID_SCORE_CATEGORIES}
        evidence = [{"counted_in_score": True}]
        result = validate_score_breakdown(breakdown, evidence)
        for cat in VALID_SCORE_CATEGORIES:
            self.assertLessEqual(result[cat], SCORE_CAPS[cat])

    def test_zeroed_when_no_counted_evidence(self):
        breakdown = {cat: 1.0 for cat in VALID_SCORE_CATEGORIES}
        result = validate_score_breakdown(breakdown, [])
        for cat in VALID_SCORE_CATEGORIES:
            self.assertEqual(result[cat], 0.0)
        self.assertEqual(result["total"], 0.0)

    def test_total_capped_at_ten(self):
        breakdown = {cat: SCORE_CAPS[cat] for cat in VALID_SCORE_CATEGORIES}
        evidence = [{"counted_in_score": True}]
        result = validate_score_breakdown(breakdown, evidence)
        self.assertLessEqual(result["total"], TOTAL_SCORE_CAP)

    def test_non_dict_input_handled(self):
        result = validate_score_breakdown(None, [{"counted_in_score": True}])
        for cat in VALID_SCORE_CATEGORIES:
            self.assertEqual(result[cat], 0.0)


# ── Fallback and error paths ──────────────────────────────────────────────────

class TestFallbackPaths(unittest.TestCase):

    def test_safe_fallback_structure(self):
        agent = HiringPatternAgent.__new__(HiringPatternAgent)
        result = agent._safe_fallback("Acme Corp", "acmecorp.com", "API key missing")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["sonar_relevance_score"], 0)
        self.assertIn("API key missing", result["limitations"])
        for cat in VALID_SCORE_CATEGORIES:
            self.assertIn(cat, result["score_breakdown"])

    @patch("agents.hiring.agent.ANTHROPIC_API_KEY", "")
    def test_no_api_key_returns_error(self):
        agent = HiringPatternAgent.__new__(HiringPatternAgent)
        result = agent.run("Acme Corp", "acmecorp.com")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["sonar_relevance_score"], 0)

    @patch("agents.hiring.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_malformed_json_returns_error(self):
        agent, mock_client = _make_agent_with_mock_client()
        mock_client.messages.create.return_value = _mock_end_turn_response(
            "This is not JSON at all."
        )
        result = agent.run("Acme Corp", "acmecorp.com")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["sonar_relevance_score"], 0)

    @patch("agents.hiring.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_empty_response_returns_error(self):
        agent, mock_client = _make_agent_with_mock_client()
        mock_client.messages.create.return_value = _mock_end_turn_response("")
        result = agent.run("Acme Corp", "acmecorp.com")
        self.assertEqual(result["status"], "error")

    @patch("agents.hiring.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_api_exception_returns_error(self):
        agent, mock_client = _make_agent_with_mock_client()
        mock_client.messages.create.side_effect = RuntimeError("connection refused")
        result = agent.run("Acme Corp", "acmecorp.com")
        self.assertEqual(result["status"], "error")
        self.assertTrue(any("connection refused" in lim for lim in result["limitations"]))


# ── Confidence and status normalisation ──────────────────────────────────────

class TestStatusAndConfidenceNormalisation(unittest.TestCase):

    @patch("agents.hiring.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_invalid_status_normalised_to_partial(self):
        bad = json.loads(_valid_response())
        bad["status"] = "mystery_status"

        agent, mock_client = _make_agent_with_mock_client()
        mock_client.messages.create.return_value = _mock_end_turn_response(json.dumps(bad))
        result = agent.run("Acme Corp", "acmecorp.com")

        self.assertEqual(result["status"], "partial")

    @patch("agents.hiring.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_invalid_confidence_normalised_to_low(self):
        bad = json.loads(_valid_response())
        bad["confidence"] = "Very High"

        agent, mock_client = _make_agent_with_mock_client()
        mock_client.messages.create.return_value = _mock_end_turn_response(json.dumps(bad))
        result = agent.run("Acme Corp", "acmecorp.com")

        self.assertEqual(result["confidence"], "Low")

    @patch("agents.hiring.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_loop_limitations_appended(self):
        agent, mock_client = _make_agent_with_mock_client()

        # First call triggers tool_use, second ends the turn
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tu_001"
        tool_resp = MagicMock()
        tool_resp.stop_reason = "tool_use"
        tool_resp.content = [tool_block]

        end_block = MagicMock()
        end_block.type = "text"
        end_block.text = _valid_response()
        end_resp = MagicMock()
        end_resp.stop_reason = "end_turn"
        end_resp.content = [end_block]

        mock_client.messages.create.side_effect = [tool_resp, end_resp]

        result = agent.run("Acme Corp", "acmecorp.com")
        self.assertIn("sonar_relevance_score", result)


# ── JSON extraction edge cases ────────────────────────────────────────────────

class TestJsonExtraction(unittest.TestCase):

    def _agent(self) -> HiringPatternAgent:
        return HiringPatternAgent.__new__(HiringPatternAgent)

    def test_strips_markdown_fences(self):
        payload = '{"company": "X", "status": "no_data", "evidence": []}'
        wrapped = f"```json\n{payload}\n```"
        result = self._agent()._safe_json_loads(wrapped)
        self.assertEqual(result["company"], "X")

    def test_brace_counting_extracts_embedded_json(self):
        payload = json.dumps({"signal": "hiring_patterns", "evidence": []})
        text = f"Here is the result:\n{payload}\nThat's all."
        result = self._agent()._safe_json_loads(text)
        self.assertEqual(result["signal"], "hiring_patterns")

    def test_empty_string_returns_empty_dict(self):
        result = self._agent()._safe_json_loads("")
        self.assertEqual(result, {})

    def test_no_json_returns_empty_dict(self):
        result = self._agent()._safe_json_loads("Sorry, no results found.")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
