"""
HiringPatternAgent — Velocity.

Detects public, company-linked hiring signals indicating investment in
DevSecOps, platform engineering, software delivery, or cloud scaling
that is relevant to Sonar sales outreach.

Design:
- Claude API with web_search does all discovery and analysis.
- Python builds the prompt, validates JSON shape, enforces score caps,
  and returns a safe fallback on failure.
- Claude must NOT invent job postings or attribute generic signals to the company.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from agents.base import BaseAgent
from agents.hiring.claude_job_search import run_job_search
from agents.hiring.config import (
    SCORE_CAPS,
    TOTAL_SCORE_CAP,
    VALID_SCORE_CATEGORIES,
    VALID_STATUSES,
    VALID_CONFIDENCE,
)
from agents.hiring.models import validate_evidence_item, validate_score_breakdown
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
            kept.append(item)  # unparseable date — keep it
    return kept


class HiringPatternAgent(BaseAgent):

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
            raw_text, loop_limitations, loop_in, loop_out = run_job_search(
                client=self.client,
                model=self.model,
                system_prompt=system_prompt,
                user_message=user_message,
            )
        except Exception as e:
            return self._safe_fallback(company, domain, f"Job search API error: {e}")

        usage = {"input": loop_in, "output": loop_out}

        if not raw_text:
            return self._safe_fallback(
                company, domain, "Job search returned no usable response", usage=usage,
            )

        result = self._parse_response(raw_text)
        if result is None:
            return self._safe_fallback(
                company, domain,
                f"Could not parse job search response as JSON. "
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
        search_queries = self._build_search_queries(company, domain)

        context_parts = []
        if country:
            context_parts.append(f"Country: {country}")
        if industry:
            context_parts.append(f"Industry: {industry}")
        context_line = "\n".join(context_parts) if context_parts else ""

        cutoff = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return (
            f"## Target Company\n\n"
            f"Company: {company}\n"
            f"Domain: {domain or 'not provided'}\n"
            + (f"{context_line}\n" if context_line else "")
            + f"\n## Search Queries\n\n"
            f"Run searches using combinations of the queries below. "
            f"Search broadly but filter strictly — only keep results "
            f"clearly tied to {company}.\n\n"
            f"{search_queries}\n\n"
            "## Attribution reminder\n\n"
            f"Only include evidence that is clearly linked to {company}. "
            "No company link = no hiring signal. "
            "Do not guess. Do not use generic market signals. "
            "Do not attribute a job posting to the company unless public evidence confirms it.\n\n"
            "## Recency rule\n\n"
            f"Today is {cutoff}. "
            "Only include job postings dated within the last 90 days. "
            "Skip any posting older than 90 days — do not include it in evidence at all. "
            "For each evidence item, record the posting date in the date_posted field "
            "(ISO format YYYY-MM-DD). If the date cannot be determined, set date_posted to null.\n\n"
            "## Required output\n\n"
            "Return ONLY valid JSON with this exact schema. "
            "No markdown fences. No text before or after.\n\n"
            + self._json_schema_example(company, domain)
        )

    def _build_search_queries(self, company: str, domain: str) -> str:
        cq = f'"{company}"'

        ats_queries = "\n".join([
            f'- site:greenhouse.io {cq}',
            f'- site:lever.co {cq}',
            f'- site:ashbyhq.com {cq}',
            f'- site:myworkdayjobs.com {cq}',
            f'- site:smartrecruiters.com {cq}',
            f'- site:teamtailor.com {cq}',
        ])

        role_queries = "\n".join([
            f'- {cq} "application security engineer" OR "appsec engineer" jobs',
            f'- {cq} "devsecops engineer" OR "DevSecOps" jobs',
            f'- {cq} "product security engineer" OR "secure SDLC" jobs',
            f'- {cq} "platform engineer" OR "devops engineer" jobs',
            f'- {cq} "site reliability engineer" OR "SRE" jobs',
            f'- {cq} "software engineer" OR "backend engineer" jobs',
            f'- {cq} "cloud engineer" OR "infrastructure engineer" jobs',
            f'- {cq} "security engineer" OR "security architect" jobs',
            f'- {cq} "CI/CD engineer" OR "build engineer" jobs',
        ])

        careers_queries = "\n".join([
            f'- {cq} careers engineering',
            f'- {cq} jobs hiring developers',
            f'- site:linkedin.com/jobs {cq}',
        ])

        site_queries_parts = []
        if domain:
            site_queries_parts += [
                f'- site:{domain} careers OR jobs',
                f'- site:{domain} engineering jobs',
            ]
        site_queries = "\n".join(site_queries_parts)

        result = (
            f"**ATS platform searches:**\n{ats_queries}\n\n"
            f"**Role-specific searches:**\n{role_queries}\n\n"
            f"**Careers page searches:**\n{careers_queries}\n"
        )
        if site_queries:
            result += f"\n**Company domain searches:**\n{site_queries}\n"
        return result

    def _json_schema_example(self, company: str, domain: str) -> str:
        return (
            '{\n'
            f'  "company": "{company}",\n'
            f'  "domain": "{domain}",\n'
            '  "signal": "hiring_patterns",\n'
            '  "status": "completed | partial | no_data | error",\n'
            '  "detected_categories": ["devsecops_appsec", "..."],\n'
            '  "sonar_relevance_score": 0,\n'
            '  "score_breakdown": {\n'
            '    "devsecops_appsec": 0,\n'
            '    "devops_platform": 0,\n'
            '    "software_engineering_growth": 0,\n'
            '    "cloud_infrastructure": 0,\n'
            '    "security_compliance": 0,\n'
            '    "recency_bonus": 0,\n'
            '    "total": 0\n'
            '  },\n'
            '  "summary": "2-3 sentence summary of company-linked hiring signals found",\n'
            '  "sonar_relevance_reason": "why this hiring pattern is relevant to Sonar",\n'
            '  "confidence": "High | Medium | Low",\n'
            '  "evidence": [\n'
            '    {\n'
            '      "id": "hire_001",\n'
            '      "type": "devsecops_appsec",\n'
            '      "value": "Application Security Engineer",\n'
            '      "source_type": "ats_platform | careers_page | linkedin | job_board | claude_web_search_result",\n'
            '      "source_url": "https://...",\n'
            '      "title": "short title of the job posting or page",\n'
            '      "evidence_text": "what was found, 1-2 sentences",\n'
            '      "date_posted": "YYYY-MM-DD or null if unknown",\n'
            '      "company_match": "High | Medium | Low",\n'
            '      "confidence": "High | Medium | Low",\n'
            '      "counted_in_score": true\n'
            '    }\n'
            '  ],\n'
            '  "limitations": ["any caveats or gaps in research"],\n'
            '  "sources_checked": [\n'
            '    {\n'
            '      "url": "https://...",\n'
            '      "source_type": "ats_platform",\n'
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

        data["signal"] = "hiring_patterns"

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

        # Drop postings older than 90 days
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
            "signal": "hiring_patterns",
            "status": "error",
            "detected_categories": [],
            "sonar_relevance_score": 0,
            "score_breakdown": {cat: 0.0 for cat in VALID_SCORE_CATEGORIES} | {"total": 0.0},
            "summary": "",
            "sonar_relevance_reason": "",
            "confidence": "Low",
            "evidence": [],
            "limitations": [reason],
            "sources_checked": [],
            "_usage": usage or {"input": 0, "output": 0},
        }
