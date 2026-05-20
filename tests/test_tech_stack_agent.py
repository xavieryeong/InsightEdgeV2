"""
Tests for the Velocity TechStackAgent (Claude-native design).

Run with:  python -m pytest tests/test_tech_stack_agent.py -v
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from agents.tech_stack.agent import TechStackAgent
from agents.tech_stack.models import (
    validate_evidence_item,
    validate_grouped_item,
    rebuild_grouped_lists,
    validate_score_breakdown,
)
from agents.tech_stack.config import SCORE_CAPS, VALID_SCORE_CATEGORIES, TOTAL_SCORE_CAP


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_agent() -> TechStackAgent:
    agent = TechStackAgent.__new__(TechStackAgent)
    agent.client = MagicMock()
    agent.model = "claude-test-model"
    return agent


def _mock_end_turn(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = [block]
    return resp


def _valid_response() -> str:
    return json.dumps({
        "company": "Acme Corp",
        "domain": "acmecorp.com",
        "signal": "tech_stack",
        "status": "completed",
        "detected_categories": ["relevant_languages", "ci_cd_maturity", "cloud_native_presence"],
        "sonar_relevance_score": 7.5,
        "score_breakdown": {
            "relevant_languages": 3.0,
            "ci_cd_maturity": 2.5,
            "cloud_native_presence": 1.5,
            "security_tooling_signal": 0.5,
            "engineering_visibility": 0.0,
            "total": 7.5,
        },
        "summary": "Public GitHub signals suggest Acme Corp uses Java and TypeScript.",
        "sonar_relevance_reason": "Java and TypeScript repos with GitHub Actions CI.",
        "confidence": "High",
        "languages": [
            {"name": "Java", "confidence": "High", "evidence_ids": ["tech_001"]},
            {"name": "TypeScript", "confidence": "High", "evidence_ids": ["tech_002"]},
        ],
        "cicd_tools": [
            {"name": "GitHub Actions", "confidence": "High", "evidence_ids": ["tech_003"]},
        ],
        "cloud": [
            {"name": "AWS", "confidence": "Medium", "evidence_ids": ["tech_004"]},
        ],
        "security_tools": [
            {"name": "Snyk", "confidence": "Medium", "evidence_ids": ["tech_005"]},
        ],
        "evidence": [
            {
                "id": "tech_001",
                "category": "relevant_languages",
                "name": "Java",
                "source_type": "github",
                "source_url": "https://github.com/acmecorp/backend",
                "evidence_text": "Java is the primary language in acmecorp/backend.",
                "confidence": "High",
                "counted_in_score": True,
            },
            {
                "id": "tech_002",
                "category": "relevant_languages",
                "name": "TypeScript",
                "source_type": "github",
                "source_url": "https://github.com/acmecorp/frontend",
                "evidence_text": "TypeScript used in acmecorp/frontend repo.",
                "confidence": "High",
                "counted_in_score": True,
            },
            {
                "id": "tech_003",
                "category": "ci_cd_maturity",
                "name": "GitHub Actions",
                "source_type": "github",
                "source_url": "https://github.com/acmecorp/backend/blob/main/.github/workflows",
                "evidence_text": "GitHub Actions workflow files found in backend repo.",
                "confidence": "High",
                "counted_in_score": True,
            },
            {
                "id": "tech_004",
                "category": "cloud_native_presence",
                "name": "AWS",
                "source_type": "engineering_blog",
                "source_url": "https://engineering.acmecorp.com/aws-migration",
                "evidence_text": "Acme Corp engineering blog describes AWS migration.",
                "confidence": "Medium",
                "counted_in_score": True,
            },
            {
                "id": "tech_005",
                "category": "security_tooling_signal",
                "name": "Snyk",
                "source_type": "github",
                "source_url": "https://github.com/acmecorp/backend",
                "evidence_text": "Snyk badge found in acmecorp/backend README.",
                "confidence": "Medium",
                "counted_in_score": True,
            },
        ],
        "limitations": [],
        "sources_checked": [
            {"url": "https://github.com/acmecorp", "source_type": "github",
             "status": "fetched", "notes": ""},
        ],
    })


# ── Output structure ──────────────────────────────────────────────────────────

class TestOutputStructure(unittest.TestCase):

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_all_required_keys_present(self):
        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(_valid_response())

        result = agent.run("Acme Corp", "acmecorp.com")

        required = [
            "company", "domain", "signal", "status", "detected_categories",
            "sonar_relevance_score", "score_breakdown", "summary",
            "sonar_relevance_reason", "confidence", "languages", "cicd_tools",
            "cloud", "security_tools", "evidence", "limitations", "sources_checked",
        ]
        for key in required:
            self.assertIn(key, result, f"Missing key: {key}")

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_signal_field_is_tech_stack(self):
        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(_valid_response())
        result = agent.run("Acme Corp", "acmecorp.com")
        self.assertEqual(result["signal"], "tech_stack")

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_score_breakdown_has_all_categories(self):
        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(_valid_response())
        result = agent.run("Acme Corp", "acmecorp.com")
        for cat in VALID_SCORE_CATEGORIES:
            self.assertIn(cat, result["score_breakdown"])
        self.assertIn("total", result["score_breakdown"])

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_company_domain_set(self):
        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(_valid_response())
        result = agent.run("Acme Corp", "acmecorp.com", country="US", industry="SaaS")
        self.assertEqual(result["company"], "Acme Corp")
        self.assertEqual(result["domain"], "acmecorp.com")


# ── Score enforcement ─────────────────────────────────────────────────────────

class TestScoreEnforcement(unittest.TestCase):

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_score_capped_per_category(self):
        inflated = json.loads(_valid_response())
        for cat in VALID_SCORE_CATEGORIES:
            inflated["score_breakdown"][cat] = 99.0
        inflated["score_breakdown"]["total"] = 999.0

        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(json.dumps(inflated))
        result = agent.run("Acme Corp", "acmecorp.com")

        for cat, cap in SCORE_CAPS.items():
            self.assertLessEqual(result["score_breakdown"][cat], cap)
        self.assertLessEqual(result["sonar_relevance_score"], TOTAL_SCORE_CAP)

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_no_counted_evidence_forces_zero_score(self):
        no_ev = json.loads(_valid_response())
        for ev in no_ev["evidence"]:
            ev["counted_in_score"] = False
        no_ev["score_breakdown"]["relevant_languages"] = 3.0
        no_ev["score_breakdown"]["total"] = 3.0

        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(json.dumps(no_ev))
        result = agent.run("Acme Corp", "acmecorp.com")

        self.assertEqual(result["sonar_relevance_score"], 0)
        self.assertEqual(result["score_breakdown"]["total"], 0)
        self.assertEqual(result["status"], "no_data")

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_total_equals_sum_of_categories(self):
        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(_valid_response())
        result = agent.run("Acme Corp", "acmecorp.com")

        computed = sum(result["score_breakdown"][c] for c in VALID_SCORE_CATEGORIES)
        self.assertAlmostEqual(
            result["score_breakdown"]["total"],
            min(computed, TOTAL_SCORE_CAP),
            places=5,
        )


# ── Grouped list handling ─────────────────────────────────────────────────────

class TestGroupedLists(unittest.TestCase):

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_grouped_lists_populated(self):
        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(_valid_response())
        result = agent.run("Acme Corp", "acmecorp.com")

        self.assertTrue(len(result["languages"]) > 0)
        self.assertTrue(len(result["cicd_tools"]) > 0)
        self.assertTrue(len(result["cloud"]) > 0)
        self.assertTrue(len(result["security_tools"]) > 0)

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_grouped_items_have_required_fields(self):
        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(_valid_response())
        result = agent.run("Acme Corp", "acmecorp.com")

        for group_key in ("languages", "cicd_tools", "cloud", "security_tools"):
            for item in result[group_key]:
                self.assertIn("name", item)
                self.assertIn("confidence", item)
                self.assertIn("evidence_ids", item)
                self.assertIsInstance(item["evidence_ids"], list)

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_grouped_lists_rebuilt_from_evidence_when_missing(self):
        response = json.loads(_valid_response())
        response["languages"] = []
        response["cicd_tools"] = []
        response["cloud"] = []
        response["security_tools"] = []

        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(json.dumps(response))
        result = agent.run("Acme Corp", "acmecorp.com")

        self.assertTrue(len(result["languages"]) > 0, "languages should be rebuilt from evidence")
        self.assertTrue(len(result["cicd_tools"]) > 0, "cicd_tools should be rebuilt from evidence")

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_evidence_ids_reference_valid_evidence(self):
        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(_valid_response())
        result = agent.run("Acme Corp", "acmecorp.com")

        ev_ids = {e["id"] for e in result["evidence"]}
        for group_key in ("languages", "cicd_tools", "cloud", "security_tools"):
            for item in result[group_key]:
                for eid in item.get("evidence_ids", []):
                    self.assertIn(eid, ev_ids, f"evidence_id {eid} in {group_key} not in evidence list")


# ── Evidence validation ───────────────────────────────────────────────────────

class TestEvidenceValidation(unittest.TestCase):

    def test_invalid_category_normalised(self):
        item = {"category": "invented_category", "counted_in_score": True,
                "source_url": "https://x.com", "confidence": "High"}
        result = validate_evidence_item(item, 0)
        self.assertEqual(result["category"], "relevant_languages")

    def test_invalid_confidence_normalised(self):
        item = {"confidence": "Ultra", "counted_in_score": True}
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

    def test_repo_url_alias_set(self):
        item = {"source_url": "https://github.com/acme/repo", "confidence": "High"}
        result = validate_evidence_item(item, 0)
        self.assertEqual(result["repo_url"], "https://github.com/acme/repo")

    def test_defaults_populated(self):
        result = validate_evidence_item({}, 4)
        self.assertEqual(result["id"], "tech_005")
        self.assertEqual(result["source_type"], "claude_web_search_result")
        self.assertEqual(result["confidence"], "Low")


# ── Rebuild grouped lists ─────────────────────────────────────────────────────

class TestRebuildGroupedLists(unittest.TestCase):

    def test_languages_rebuilt_correctly(self):
        evidence = [
            {"id": "t1", "category": "relevant_languages", "name": "Java",
             "confidence": "High", "counted_in_score": True},
            {"id": "t2", "category": "relevant_languages", "name": "Python",
             "confidence": "Medium", "counted_in_score": True},
        ]
        result = rebuild_grouped_lists(evidence)
        names = {item["name"] for item in result["languages"]}
        self.assertIn("Java", names)
        self.assertIn("Python", names)

    def test_deduplicates_by_name_keeping_highest_confidence(self):
        evidence = [
            {"id": "t1", "category": "relevant_languages", "name": "Java",
             "confidence": "Low", "counted_in_score": True},
            {"id": "t2", "category": "relevant_languages", "name": "Java",
             "confidence": "High", "counted_in_score": True},
        ]
        result = rebuild_grouped_lists(evidence)
        java_items = [i for i in result["languages"] if i["name"] == "Java"]
        self.assertEqual(len(java_items), 1)
        self.assertEqual(java_items[0]["confidence"], "High")

    def test_engineering_visibility_not_in_any_group(self):
        evidence = [
            {"id": "t1", "category": "engineering_visibility", "name": "Public GitHub Org",
             "confidence": "High", "counted_in_score": True},
        ]
        result = rebuild_grouped_lists(evidence)
        for group_key in ("languages", "cicd_tools", "cloud", "security_tools"):
            self.assertEqual(result[group_key], [])

    def test_empty_evidence_returns_empty_groups(self):
        result = rebuild_grouped_lists([])
        for group_key in ("languages", "cicd_tools", "cloud", "security_tools"):
            self.assertEqual(result[group_key], [])


# ── Score breakdown validation ────────────────────────────────────────────────

class TestScoreBreakdownValidation(unittest.TestCase):

    def test_clamped_to_caps(self):
        breakdown = {cat: 99.0 for cat in VALID_SCORE_CATEGORIES}
        evidence = [{"counted_in_score": True}]
        result = validate_score_breakdown(breakdown, evidence)
        for cat in VALID_SCORE_CATEGORIES:
            self.assertLessEqual(result[cat], SCORE_CAPS[cat])

    def test_zeroed_when_no_counted_evidence(self):
        breakdown = {cat: 2.0 for cat in VALID_SCORE_CATEGORIES}
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
        agent = TechStackAgent.__new__(TechStackAgent)
        result = agent._safe_fallback("Acme Corp", "acmecorp.com", "API error")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["sonar_relevance_score"], 0)
        self.assertIn("API error", result["limitations"])
        for group_key in ("languages", "cicd_tools", "cloud", "security_tools"):
            self.assertEqual(result[group_key], [])
        for cat in VALID_SCORE_CATEGORIES:
            self.assertIn(cat, result["score_breakdown"])

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "")
    def test_no_api_key_returns_error(self):
        agent = TechStackAgent.__new__(TechStackAgent)
        result = agent.run("Acme Corp", "acmecorp.com")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["sonar_relevance_score"], 0)

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_malformed_json_returns_error(self):
        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn("Not JSON at all.")
        result = agent.run("Acme Corp", "acmecorp.com")
        self.assertEqual(result["status"], "error")

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_api_exception_returns_error(self):
        agent = _make_agent()
        agent.client.messages.create.side_effect = RuntimeError("timeout")
        result = agent.run("Acme Corp", "acmecorp.com")
        self.assertEqual(result["status"], "error")
        self.assertTrue(any("timeout" in lim for lim in result["limitations"]))

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_empty_response_returns_error(self):
        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn("")
        result = agent.run("Acme Corp", "acmecorp.com")
        self.assertEqual(result["status"], "error")


# ── Status and confidence normalisation ──────────────────────────────────────

class TestNormalisation(unittest.TestCase):

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_invalid_status_normalised(self):
        bad = json.loads(_valid_response())
        bad["status"] = "unknown_status"
        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(json.dumps(bad))
        result = agent.run("Acme Corp", "acmecorp.com")
        self.assertEqual(result["status"], "partial")

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_invalid_confidence_normalised(self):
        bad = json.loads(_valid_response())
        bad["confidence"] = "Very High"
        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(json.dumps(bad))
        result = agent.run("Acme Corp", "acmecorp.com")
        self.assertEqual(result["confidence"], "Low")

    @patch("agents.tech_stack.agent.ANTHROPIC_API_KEY", "fake-key")
    def test_invalid_grouped_item_source_type_normalised(self):
        bad = json.loads(_valid_response())
        bad["evidence"][0]["source_type"] = "made_up_source"
        agent = _make_agent()
        agent.client.messages.create.return_value = _mock_end_turn(json.dumps(bad))
        result = agent.run("Acme Corp", "acmecorp.com")
        self.assertEqual(result["evidence"][0]["source_type"], "claude_web_search_result")


# ── JSON extraction edge cases ────────────────────────────────────────────────

class TestJsonExtraction(unittest.TestCase):

    def _agent(self) -> TechStackAgent:
        return TechStackAgent.__new__(TechStackAgent)

    def test_strips_markdown_fences(self):
        payload = '{"signal": "tech_stack", "evidence": []}'
        result = self._agent()._safe_json_loads(f"```json\n{payload}\n```")
        self.assertEqual(result["signal"], "tech_stack")

    def test_extracts_embedded_json(self):
        payload = json.dumps({"signal": "tech_stack", "evidence": []})
        result = self._agent()._safe_json_loads(f"Here is my answer:\n{payload}\nDone.")
        self.assertEqual(result["signal"], "tech_stack")

    def test_empty_string_returns_empty_dict(self):
        self.assertEqual(self._agent()._safe_json_loads(""), {})

    def test_no_json_returns_empty_dict(self):
        self.assertEqual(self._agent()._safe_json_loads("No findings."), {})


if __name__ == "__main__":
    unittest.main()
