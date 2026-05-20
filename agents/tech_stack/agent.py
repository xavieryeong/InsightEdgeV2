"""
TechStackAgent — Velocity.

Detects public technical signals indicating a company has a software engineering
environment where Sonar is relevant: active codebase languages, CI/CD pipelines,
cloud-native presence, code security tooling, and engineering visibility.

Design:
- Claude API with web_search does all discovery and analysis.
- Python builds the prompt, validates JSON shape, enforces score caps,
  reconstructs grouped lists for rendering, and returns a safe fallback on failure.
- Claude must NOT invent technical signals or attribute technologies to the company
  without public evidence.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from agents.base import BaseAgent
from agents.tech_stack.claude_tech_search import run_tech_search
from agents.tech_stack.config import (
    SCORE_CAPS,
    TOTAL_SCORE_CAP,
    VALID_SCORE_CATEGORIES,
    VALID_STATUSES,
    VALID_CONFIDENCE,
    CATEGORY_TO_GROUP,
)
from agents.tech_stack.models import (
    validate_evidence_item,
    validate_grouped_item,
    rebuild_grouped_lists,
    validate_score_breakdown,
)
from config.settings import ANTHROPIC_API_KEY

_PROMPT_PATH = Path(__file__).parent / "prompt.md"


class TechStackAgent(BaseAgent):

    def run(
        self,
        company: str,
        domain: str = "",
        country: str = "",
        industry: str = "",
    ) -> dict:
        if not ANTHROPIC_API_KEY:
            return self._safe_fallback(company, domain, "ANTHROPIC_API_KEY is not configured")

        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        user_message = self._build_prompt(company, domain, country, industry)

        try:
            raw_text, loop_limitations, loop_in, loop_out = run_tech_search(
                client=self.client,
                model=self.model,
                system_prompt=system_prompt,
                user_message=user_message,
            )
        except Exception as e:
            return self._safe_fallback(company, domain, f"Tech search API error: {e}")

        usage = {"input": loop_in, "output": loop_out}

        if not raw_text:
            return self._safe_fallback(
                company, domain, "Tech search returned no usable response", usage=usage,
            )

        result = self._parse_response(raw_text)
        if result is None:
            return self._safe_fallback(
                company, domain,
                f"Could not parse tech search response as JSON. "
                f"Raw response (first 500 chars): {raw_text[:500]}",
                usage=usage,
            )

        result["company"] = company
        result["domain"] = domain
        result.setdefault("country", country)
        result.setdefault("industry", industry)

        if loop_limitations:
            result.setdefault("limitations", [])
            result["limitations"].extend(loop_limitations)

        result["_usage"] = usage
        return result

    # ── Prompt builder ────────────────────────────────────────────────────────

    def _build_prompt(
        self,
        company: str,
        domain: str,
        country: str,
        industry: str,
    ) -> str:
        context_parts = []
        if country:
            context_parts.append(f"Country: {country}")
        if industry:
            context_parts.append(f"Industry: {industry}")
        context_line = "\n".join(context_parts)

        search_queries = self._build_search_queries(company, domain)

        return (
            f"## Target Company\n\n"
            f"Company: {company}\n"
            f"Domain: {domain or 'not provided'}\n"
            + (f"{context_line}\n" if context_line else "")
            + f"\n## Search Queries\n\n"
            f"Run searches using combinations of the queries below. "
            f"Search broadly but filter strictly — only keep findings clearly "
            f"tied to {company}.\n\n"
            f"{search_queries}\n\n"
            "## Attribution reminder\n\n"
            f"Only include evidence that is clearly linked to {company}. "
            "Do not infer technologies from company size, industry, or country. "
            "Do not attribute a technology unless public evidence names {company} explicitly.\n\n"
            "## Required output\n\n"
            "Return ONLY valid JSON with this exact schema. "
            "No markdown fences. No text before or after.\n\n"
            + self._json_schema_example(company, domain)
        )

    def _build_search_queries(self, company: str, domain: str) -> str:
        cq = f'"{company}"'

        github_queries = "\n".join([
            f'- site:github.com {cq}',
            f'- {cq} github.com open source repositories',
            f'- {cq} language:Java OR language:TypeScript OR language:Python github',
            f'- {cq} language:C# OR language:"C++" OR language:Go github',
        ])

        tech_stack_queries = "\n".join([
            f'- {cq} technology stack',
            f'- {cq} tech stack built with',
            f'- {cq} site:stackshare.io',
            f'- {cq} site:stackoverview.com OR site:siftery.com',
        ])

        cicd_queries = "\n".join([
            f'- {cq} "GitHub Actions" OR Jenkins OR "GitLab CI"',
            f'- {cq} "Azure DevOps" OR CircleCI OR "Travis CI"',
            f'- {cq} CI/CD pipeline delivery',
        ])

        cloud_queries = "\n".join([
            f'- {cq} AWS OR Azure OR "Google Cloud" cloud',
            f'- {cq} Kubernetes OR Docker OR Terraform',
            f'- {cq} cloud-native microservices infrastructure',
        ])

        security_queries = "\n".join([
            f'- {cq} SonarQube OR SonarCloud',
            f'- {cq} Snyk OR Checkmarx OR Veracode OR Semgrep',
            f'- {cq} code security static analysis SAST',
        ])

        blog_queries_parts = [
            f'- {cq} engineering blog technology',
            f'- {cq} developer documentation API',
        ]
        if domain:
            blog_queries_parts += [
                f'- site:{domain} engineering OR tech OR developer blog',
                f'- site:{domain} technology stack OR open source',
            ]
        blog_queries = "\n".join(blog_queries_parts)

        return (
            f"**GitHub / open-source searches:**\n{github_queries}\n\n"
            f"**Tech stack listing searches:**\n{tech_stack_queries}\n\n"
            f"**CI/CD searches:**\n{cicd_queries}\n\n"
            f"**Cloud / infrastructure searches:**\n{cloud_queries}\n\n"
            f"**Security tooling searches:**\n{security_queries}\n\n"
            f"**Engineering blog / docs searches:**\n{blog_queries}\n"
        )

    def _json_schema_example(self, company: str, domain: str) -> str:
        return (
            '{\n'
            f'  "company": "{company}",\n'
            f'  "domain": "{domain}",\n'
            '  "signal": "tech_stack",\n'
            '  "status": "completed | partial | no_data | error",\n'
            '  "detected_categories": ["relevant_languages", "ci_cd_maturity"],\n'
            '  "sonar_relevance_score": 0,\n'
            '  "score_breakdown": {\n'
            '    "relevant_languages": 0,\n'
            '    "ci_cd_maturity": 0,\n'
            '    "cloud_native_presence": 0,\n'
            '    "security_tooling_signal": 0,\n'
            '    "engineering_visibility": 0,\n'
            '    "total": 0\n'
            '  },\n'
            '  "summary": "2-3 sentence summary of public technical signals found",\n'
            '  "sonar_relevance_reason": "why this tech stack is relevant to Sonar",\n'
            '  "confidence": "High | Medium | Low",\n'
            '  "languages": [\n'
            '    {"name": "Java", "confidence": "High", "evidence_ids": ["tech_001"]}\n'
            '  ],\n'
            '  "cicd_tools": [\n'
            '    {"name": "GitHub Actions", "confidence": "High", "evidence_ids": ["tech_002"]}\n'
            '  ],\n'
            '  "cloud": [\n'
            '    {"name": "AWS", "confidence": "Medium", "evidence_ids": ["tech_003"]}\n'
            '  ],\n'
            '  "security_tools": [\n'
            '    {"name": "Snyk", "confidence": "Medium", "evidence_ids": ["tech_004"]}\n'
            '  ],\n'
            '  "evidence": [\n'
            '    {\n'
            '      "id": "tech_001",\n'
            '      "category": "relevant_languages | ci_cd_maturity | cloud_native_presence | security_tooling_signal | engineering_visibility",\n'
            '      "name": "specific technology name",\n'
            '      "source_type": "github | engineering_blog | tech_listing | developer_docs | claude_web_search_result",\n'
            '      "source_url": "https://...",\n'
            '      "evidence_text": "what was found, 1-2 sentences",\n'
            '      "confidence": "High | Medium | Low",\n'
            '      "counted_in_score": true\n'
            '    }\n'
            '  ],\n'
            '  "limitations": ["any caveats or gaps in research"],\n'
            '  "sources_checked": [\n'
            '    {\n'
            '      "url": "https://...",\n'
            '      "source_type": "github",\n'
            '      "status": "searched | fetched | failed | blocked",\n'
            '      "notes": ""\n'
            '    }\n'
            '  ]\n'
            '}'
        )

    # ── Response parsing and validation ──────────────────────────────────────

    def _parse_response(self, text: str) -> dict | None:
        data = self._safe_json_loads(text)
        if not isinstance(data, dict) or not data:
            return None

        data["signal"] = "tech_stack"

        if data.get("status") not in VALID_STATUSES:
            data["status"] = "partial"

        if data.get("confidence") not in VALID_CONFIDENCE:
            data["confidence"] = "Low"

        for field in ("summary", "sonar_relevance_reason"):
            if not isinstance(data.get(field), str):
                data[field] = ""

        for field in ("detected_categories", "evidence", "limitations", "sources_checked"):
            if not isinstance(data.get(field), list):
                data[field] = []

        # Validate evidence items
        valid_evidence = []
        for i, item in enumerate(data["evidence"]):
            if not isinstance(item, dict):
                continue
            valid_evidence.append(validate_evidence_item(item, i))
        data["evidence"] = valid_evidence

        # Validate and enforce score breakdown
        data["score_breakdown"] = validate_score_breakdown(
            data.get("score_breakdown", {}),
            valid_evidence,
        )
        data["sonar_relevance_score"] = data["score_breakdown"]["total"]

        # Force no_data if score is 0 and no counted evidence
        if data["sonar_relevance_score"] == 0 and not any(
            e.get("counted_in_score") for e in valid_evidence
        ):
            data["status"] = "no_data"

        # Validate grouped lists — fall back to rebuilding from evidence if missing/empty
        for group_key in ("languages", "cicd_tools", "cloud", "security_tools"):
            raw = data.get(group_key)
            if isinstance(raw, list) and raw:
                data[group_key] = [
                    validate_grouped_item(item)
                    for item in raw
                    if isinstance(item, dict)
                ]
            else:
                data[group_key] = []

        # If ALL grouped lists are empty but evidence exists, rebuild from evidence
        if not any(data[g] for g in ("languages", "cicd_tools", "cloud", "security_tools")):
            rebuilt = rebuild_grouped_lists(valid_evidence)
            for group_key, items in rebuilt.items():
                if items:
                    data[group_key] = items

        # Validate sources_checked
        valid_sources = []
        for src in data["sources_checked"]:
            if not isinstance(src, dict):
                continue
            src.setdefault("url", "")
            src.setdefault("source_type", "")
            src.setdefault("status", "searched")
            src.setdefault("notes", "")
            valid_sources.append(src)
        data["sources_checked"] = valid_sources

        return data

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _safe_json_loads(self, text: str) -> dict:
        text = text.strip()
        text = re.sub(r"```(?:json)?", "", text).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Brace-counting extractor
        start = text.find("{")
        if start == -1:
            return {}
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        return {}

    def _safe_fallback(
        self, company: str, domain: str, reason: str, usage: dict | None = None,
    ) -> dict:
        return {
            "company": company,
            "domain": domain,
            "signal": "tech_stack",
            "status": "error",
            "detected_categories": [],
            "sonar_relevance_score": 0,
            "score_breakdown": {cat: 0.0 for cat in VALID_SCORE_CATEGORIES} | {"total": 0.0},
            "summary": "",
            "sonar_relevance_reason": "",
            "confidence": "Low",
            "languages": [],
            "cicd_tools": [],
            "cloud": [],
            "security_tools": [],
            "evidence": [],
            "limitations": [reason],
            "sources_checked": [],
            "_usage": usage or {"input": 0, "output": 0},
        }
