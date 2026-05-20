"""
PainPointAgent — Velocity only.

Detects public, company-linked developer pain signals for Sonar sales.

Design:
- Claude API with web_search does the discovery and research.
- Python builds the prompt, validates the JSON shape, enforces score safety rules,
  and returns a safe fallback on failure.
- Claude must NOT invent pain or attribute generic signals to the company.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from agents.base import BaseAgent
from agents.pain_points.claude_pain_search import run_pain_search
from agents.pain_points.config import (
    SCORE_CAPS,
    TOTAL_SCORE_CAP,
    VALID_SCORE_CATEGORIES,
    VALID_STATUSES,
    VALID_CONFIDENCE,
)
from agents.pain_points.models import validate_evidence_item, validate_score_breakdown
from config.settings import ANTHROPIC_API_KEY

_PROMPT_PATH = Path(__file__).parent / "prompt.md"
_90_DAYS = 90


def _filter_stale_evidence(evidence: list[dict]) -> list[dict]:
    """Remove evidence items where date_posted is older than 90 days. Items with no date pass through."""
    cutoff = datetime.now(timezone.utc).toordinal() - _90_DAYS
    kept = []
    for item in evidence:
        raw = item.get("date_posted")
        if not raw or not isinstance(raw, str):
            kept.append(item)
            continue
        try:
            posted = datetime.fromisoformat(raw.strip()).toordinal()
            if posted >= cutoff:
                kept.append(item)
        except ValueError:
            kept.append(item)
    return kept


class PainPointAgent(BaseAgent):

    def run(
        self,
        company: str,
        domain: str = "",
        country: str = "",
        industry: str = "",
        tech_stack_result: dict | None = None,
        hiring_result: dict | None = None,
        news_result: dict | None = None,
    ) -> dict:
        if not ANTHROPIC_API_KEY:
            return self._safe_fallback(company, domain, "ANTHROPIC_API_KEY is not configured")

        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        user_message = self._build_prompt(
            company, domain, country, industry,
            tech_stack_result, hiring_result, news_result,
        )

        try:
            raw_text, loop_limitations, loop_in, loop_out = run_pain_search(
                client=self.client,
                model=self.model,
                system_prompt=system_prompt,
                user_message=user_message,
            )
        except Exception as e:
            return self._safe_fallback(company, domain, f"Pain search API error: {e}")

        usage = {"input": loop_in, "output": loop_out}

        if not raw_text:
            return self._safe_fallback(
                company, domain, "Pain search returned no usable response", usage=usage,
            )

        result = self._parse_response(raw_text)
        if result is None:
            return self._safe_fallback(
                company, domain,
                f"Could not parse pain search response as JSON. "
                f"Raw response (first 500 chars): {raw_text[:500]}",
                usage=usage,
            )

        result["company"] = company
        result["domain"] = domain

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
        tech_stack_result: dict | None,
        hiring_result: dict | None,
        news_result: dict | None,
    ) -> str:
        context_hints = self._build_context_hints(
            tech_stack_result, hiring_result, news_result
        )
        search_queries = self._build_search_queries(company, domain)

        cutoff = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return (
            f"## Target Company\n\n"
            f"Company: {company}\n"
            f"Domain: {domain or 'not provided'}\n"
            f"Country: {country or 'detect from your knowledge'}\n"
            f"Industry: {industry or 'detect from your knowledge'}\n\n"
            f"{context_hints}"
            f"## Search Queries\n\n"
            f"Run searches using combinations of the queries below. "
            f"Search broadly but filter strictly — only keep results "
            f"clearly tied to {company}.\n\n"
            f"{search_queries}\n\n"
            "## Attribution reminder\n\n"
            f"Only include evidence that is clearly linked to {company}. "
            "No company link = no pain signal. "
            "Do not guess. Do not use generic developer pain. "
            "Do not attribute a signal to the company unless public evidence supports it.\n\n"
            "## Recency rule\n\n"
            f"Today is {cutoff}. "
            "Only include pain signals posted or discussed within the last 90 days. "
            "Skip any evidence older than 90 days. "
            "For each evidence item, record the date in the date_posted field "
            "(ISO format YYYY-MM-DD). If the date cannot be determined, set date_posted to null.\n\n"
            "## Required output\n\n"
            "Return ONLY valid JSON with this exact schema. "
            "No markdown fences. No text before or after.\n\n"
            + self._json_schema_example(company, domain)
        )

    def _build_context_hints(
        self,
        tech_stack_result: dict | None,
        hiring_result: dict | None,
        news_result: dict | None,
    ) -> str:
        hints: list[str] = []

        if tech_stack_result:
            langs = [t["name"] for t in tech_stack_result.get("languages", [])]
            cicd  = [t["name"] for t in tech_stack_result.get("cicd_tools", [])]
            sec   = [t["name"] for t in tech_stack_result.get("security_tools", [])]
            parts = []
            if langs: parts.append(f"languages: {', '.join(langs[:5])}")
            if cicd:  parts.append(f"CI/CD: {', '.join(cicd[:5])}")
            if sec:   parts.append(f"security tools: {', '.join(sec[:5])}")
            if parts:
                hints.append(
                    "Tech stack context — focus pain searches on these detected signals: "
                    + "; ".join(parts)
                )

        if hiring_result:
            roles = list({
                e.get("value", "")
                for e in hiring_result.get("evidence", [])
                if e.get("counted_in_score") and e.get("value")
            })[:6]
            if roles:
                hints.append(
                    "Hiring context — company is hiring for: "
                    + ", ".join(roles)
                    + ". Focus pain searches on pain related to these roles."
                )

        if news_result:
            top_news = [
                e.get("title", "")
                for e in news_result.get("evidence", [])
                if e.get("counted_in_score") and e.get("title")
            ][:3]
            if top_news:
                hints.append(
                    "Recent news context — search for pain related to these recent events: "
                    + "; ".join(top_news)
                )

        if not hints:
            return ""
        return "## Context from other agents\n\n" + "\n".join(f"- {h}" for h in hints) + "\n\n"

    def _build_search_queries(self, company: str, domain: str) -> str:
        cq = f'"{company}"'
        domain_line = f"domain: {domain}" if domain else ""

        sonar_queries = "\n".join([
            f'- {cq} SonarQube',
            f'- {cq} SonarCloud',
            f'- {cq} quality gate',
            f'- {cq} code quality',
            f'- {cq} static analysis',
            f'- {cq} SAST',
            f'- {cq} security hotspot',
            f'- {cq} false positive scanner',
            f'- {cq} CI/CD quality gate failed',
            f'- {cq} GitHub Actions Sonar',
            f'- {cq} Jenkins Sonar',
            f'- {cq} GitLab CI Sonar',
            f'- {cq} technical debt',
            f'- {cq} legacy code modernization',
            f'- {cq} code smell',
            f'- {cq} AppSec DevSecOps',
            f'- {cq} secure coding',
            f'- {cq} code vulnerability',
        ])

        security_queries = "\n".join([
            f'- {cq} hacked OR breach OR cyberattack',
            f'- {cq} ransomware',
            f'- {cq} vulnerability incident',
            f'- {cq} engineering incident',
            f'- {cq} security incident developer',
        ])

        engineering_queries = "\n".join([
            f'- {cq} developer productivity issue',
            f'- {cq} platform engineering issue',
            f'- {cq} engineering blog migration',
            f'- {cq} scaling engineering team',
            f'- {cq} release velocity pressure',
        ])

        competitor_queries = "\n".join([
            f'- {cq} Snyk OR Checkmarx OR Veracode OR Semgrep OR CodeQL pain',
            f'- {cq} static analysis tool frustration',
        ])

        site_queries_parts = [
            f'- site:github.com {cq} SonarQube OR "quality gate" OR "technical debt"',
            f'- site:community.sonarsource.com {cq}',
            f'- site:stackoverflow.com {cq} SonarQube',
            f'- site:reddit.com {cq} engineering OR hacked OR developer',
        ]
        if domain:
            site_queries_parts += [
                f'- site:{domain} engineering blog OR technical blog OR developer blog',
                f'- site:{domain} code quality OR security incident OR engineering incident',
            ]
        site_queries = "\n".join(site_queries_parts)

        return (
            f"**Sonar / code quality searches:**\n{sonar_queries}\n\n"
            f"**Security incident searches:**\n{security_queries}\n\n"
            f"**Engineering pain searches:**\n{engineering_queries}\n\n"
            f"**Competitor tooling searches:**\n{competitor_queries}\n\n"
            f"**Site-specific searches:**\n{site_queries}\n"
            + (f"\n{domain_line}" if domain_line else "")
        )

    def _json_schema_example(self, company: str, domain: str) -> str:
        return (
            '{\n'
            f'  "company": "{company}",\n'
            f'  "domain": "{domain}",\n'
            '  "signal": "pain_points",\n'
            '  "status": "completed | partial | no_data | error",\n'
            '  "detected_categories": ["security_incident_pain", "..."],\n'
            '  "sonar_relevance_score": 0,\n'
            '  "score_breakdown": {\n'
            '    "company_linked_pain": 0,\n'
            '    "security_quality_urgency": 0,\n'
            '    "delivery_pressure": 0,\n'
            '    "sonar_or_competitor_pain": 0,\n'
            '    "recency_repeat_bonus": 0,\n'
            '    "total": 0\n'
            '  },\n'
            '  "summary": "2-3 sentence summary of company-linked pain found",\n'
            '  "sonar_relevance_reason": "why this pain is relevant to Sonar",\n'
            '  "recommended_sales_angle": "practical outreach angle for a sales rep",\n'
            '  "confidence": "High | Medium | Low",\n'
            '  "evidence": [\n'
            '    {\n'
            '      "id": "pain_001",\n'
            '      "category": "security_incident_pain",\n'
            '      "source_type": "github | stackoverflow | reddit | sonar_community | company_engineering_blog | company_forum | claude_web_search_result",\n'
            '      "source_url": "https://...",\n'
            '      "title": "short title of the evidence",\n'
            '      "evidence_text": "what was found, 1-3 sentences",\n'
            '      "date_posted": "YYYY-MM-DD or null if unknown",\n'
            '      "matched_keywords": ["SonarQube", "quality gate"],\n'
            '      "company_match": "High | Medium | Low",\n'
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

        data["signal"] = "pain_points"

        if data.get("status") not in VALID_STATUSES:
            data["status"] = "partial"

        if data.get("confidence") not in VALID_CONFIDENCE:
            data["confidence"] = "Low"

        for field in ("summary", "sonar_relevance_reason", "recommended_sales_angle"):
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

        # Drop posts older than 90 days
        valid_evidence = _filter_stale_evidence(valid_evidence)
        data["evidence"] = valid_evidence

        # Validate and enforce score breakdown
        data["score_breakdown"] = validate_score_breakdown(
            data.get("score_breakdown", {}),
            valid_evidence,
        )
        data["sonar_relevance_score"] = data["score_breakdown"]["total"]

        # If no counted evidence, force no_data status
        if data["sonar_relevance_score"] == 0 and not any(
            e.get("counted_in_score") for e in valid_evidence
        ):
            data["status"] = "no_data"

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
            "signal": "pain_points",
            "status": "error",
            "detected_categories": [],
            "sonar_relevance_score": 0,
            "score_breakdown": {cat: 0.0 for cat in VALID_SCORE_CATEGORIES} | {"total": 0.0},
            "summary": "",
            "sonar_relevance_reason": "",
            "recommended_sales_angle": "",
            "confidence": "Low",
            "evidence": [],
            "limitations": [reason],
            "sources_checked": [],
            "_usage": usage or {"input": 0, "output": 0},
        }
