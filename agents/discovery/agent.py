from __future__ import annotations

import json
import re
from pathlib import Path

from agents.base import BaseAgent
from agents.discovery.claude_discovery_search import run_discovery_search
from agents.discovery.config import (
    MIDMARKET_MIN_EMPLOYEES,
    MIDMARKET_MAX_EMPLOYEES,
)
from config.settings import ANTHROPIC_API_KEY

_PROMPT_PATH = Path(__file__).parent / "prompt.md"

_VALID_TRIGGER_SIGNALS = {
    "hiring", "news", "tech_stack", "secure_sdlc", "engineering_scale",
}
_VALID_CONFIDENCE = {"High", "Medium", "Low"}


class CompanyDiscoveryAgent(BaseAgent):
    """
    Builds a candidate Velocity account list by searching for public buying signals.
    Returns companies discovered through signals — not from generic company directories.
    Each account includes the signal that triggered its discovery.
    """

    def run(
        self,
        countries: list[str],
        industries: list[str],
        count: int,
    ) -> tuple[list[dict], list[str]]:
        """
        Returns (accounts, limitations).
        accounts = [{company, domain, country, industry, trigger_signal,
                     signal_summary, source_type, source_url, signal_date, confidence}]
        limitations = list of strings describing any issues encountered.
        """
        if not ANTHROPIC_API_KEY:
            return [], ["ANTHROPIC_API_KEY is not configured."]

        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        user_message = self._build_prompt(countries, industries, count)

        try:
            raw_text, loop_limitations = run_discovery_search(
                client=self.client,
                model=self.model,
                system_prompt=system_prompt,
                user_message=user_message,
            )
        except Exception as e:
            return [], [f"Discovery search API error: {e}"]

        if not raw_text:
            return [], ["Discovery search returned no usable response."]

        accounts, parse_limitations = self._parse_response(raw_text, countries, industries)
        limitations = loop_limitations + parse_limitations

        # Trim to requested count after dedup
        accounts = accounts[:count]

        return accounts, limitations

    # ── Prompt builder ────────────────────────────────────────────────────────

    def _build_prompt(
        self,
        countries: list[str],
        industries: list[str],
        count: int,
    ) -> str:
        countries_str = ", ".join(countries) if countries else "any"
        industries_str = ", ".join(industries) if industries else "any"

        # Ask for more than needed to have buffer after dedup
        target = min(count + 15, count * 2)

        return (
            f"## Discovery Request\n\n"
            f"Find {target} mid-market companies showing **public buying signals** for "
            f"Sonar's code quality and application security products.\n\n"
            f"**Target criteria:**\n"
            f"- Countries: {countries_str}\n"
            f"- Industries: {industries_str}\n"
            f"- Employee count: {MIDMARKET_MIN_EMPLOYEES}–{MIDMARKET_MAX_EMPLOYEES} employees\n"
            f"- Must have an in-house software engineering or development function\n\n"
            f"## Search strategy\n\n"
            f"Do NOT search for 'companies in {countries_str}' or pull from generic directories. "
            f"Run the signal searches below. Each signal reveals a potential Sonar customer. "
            f"Extract the company name from what you find and record the triggering signal.\n\n"
            + self._build_search_queries(countries, industries)
            + "\n\n"
            "## Recency rules\n\n"
            "- Hiring signals: only count job postings from the last 90 days.\n"
            "- News signals: only count articles/announcements from the last 90 days.\n"
            "- Tech stack, secure SDLC, engineering scale: no strict date restriction.\n\n"
            "## Required output\n\n"
            "Return ONLY valid JSON with no markdown fences:\n\n"
            "{\n"
            '  "companies": [\n'
            '    {\n'
            '      "company": "Exact company name",\n'
            '      "domain": "example.com",\n'
            '      "country": "Singapore",\n'
            '      "industry": "Financial Services",\n'
            '      "trigger_signal": "hiring | news | tech_stack | secure_sdlc | engineering_scale",\n'
            '      "signal_summary": "one sentence on what signal was found and why it is relevant",\n'
            '      "source_type": "linkedin_jobs | greenhouse | lever | ashby | news | github | company_website | web_search_result",\n'
            '      "source_url": "https://... or empty string",\n'
            '      "signal_date": "YYYY-MM-DD or empty string",\n'
            '      "confidence": "High | Medium | Low"\n'
            '    }\n'
            '  ],\n'
            '  "limitations": ["any issues encountered"]\n'
            "}\n\n"
            "Rules:\n"
            "- Only include companies found through signal searches. Do not invent any.\n"
            "- domain must be root domain only (e.g. example.com — no https://, no paths).\n"
            "- Deduplicate: one entry per company.\n"
            "- Exclude large enterprises (Fortune 500, FTSE 100, DAX 40 equivalents).\n"
            "- Prefer High or Medium confidence entries over Low.\n"
            f"- Target {target} companies. Return fewer if genuine signals are scarce.\n"
        )

    def _build_search_queries(self, countries: list[str], industries: list[str]) -> str:
        geo = " OR ".join(countries[:4]) if countries else ""
        ind_quoted = " OR ".join(f'"{i}"' for i in industries[:4]) if industries else ""
        geo_ind = f"{geo} {ind_quoted}".strip()

        hiring_queries = "\n".join([
            f'- "application security engineer" OR "AppSec engineer" jobs {geo_ind}',
            f'- "product security engineer" OR "DevSecOps engineer" jobs {geo_ind}',
            f'- "security architect" OR "security engineer" jobs {geo_ind}',
            f'- "platform engineer" OR "site reliability engineer" jobs {geo_ind}',
            f'- "DevOps engineer" OR "release engineer" OR "build engineer" jobs {geo_ind}',
            f'- "cloud engineer" OR "Kubernetes engineer" OR "infrastructure engineer" jobs {geo_ind}',
            f'- "software engineer" ("Java" OR "TypeScript" OR "Python") jobs {geo_ind}',
            f'- "backend engineer" OR "full stack engineer" jobs {geo_ind}',
            f'- site:linkedin.com/jobs ("application security" OR "DevSecOps" OR "platform engineer") {geo}',
            f'- site:greenhouse.io ("security engineer" OR "platform engineer" OR "software engineer") {geo}',
            f'- site:lever.co ("application security" OR "DevSecOps" OR "cloud engineer") {geo}',
            f'- site:ashbyhq.com ("platform engineer" OR "AppSec" OR "software engineer") {geo}',
            f'- site:smartrecruiters.com ("DevSecOps" OR "application security" OR "software engineer") {geo}',
        ])

        news_queries = "\n".join([
            f'- ("AI initiative" OR "generative AI" OR "AI platform") {geo_ind} 2025',
            f'- ("cloud migration" OR "cloud-native transformation" OR "application modernization") {geo_ind} 2025',
            f'- ("platform engineering" OR "DevOps transformation" OR "developer platform") {geo_ind} 2025',
            f'- ("engineering hub" OR "R&D center" OR "engineering investment") {geo_ind} 2025',
            f'- ("new CTO" OR "new CISO" OR "VP Engineering" OR "Chief Technology Officer") {geo_ind} 2025',
            f'- ("data breach" OR "cyber attack" OR "ransomware" OR "security incident") {geo_ind} 2025',
            f'- ("vulnerability disclosure" OR "hacked" OR "data leak") {geo_ind} 2025',
            f'- ("product launch" OR "major release" OR "new platform" OR "developer platform") {geo_ind} 2025',
            f'- ("digital transformation" OR "software modernization" OR "tech overhaul") {geo_ind} 2025',
            f'- ("engineering expansion" OR "software center" OR "development center") {geo_ind} 2025',
        ])

        tech_stack_queries = "\n".join([
            f'- site:github.com ("sonarqube" OR "sonarcloud" OR "quality gate") {geo}',
            f'- site:github.com ("Jenkinsfile" OR "GitHub Actions" OR ".gitlab-ci.yml" OR "azure-pipelines") {geo}',
            f'- ("GitHub Actions" OR "Jenkins" OR "GitLab CI" OR "Azure DevOps") {geo_ind} engineering',
            f'- ("Kubernetes" OR "Docker" OR "Terraform" OR "cloud-native") {geo_ind} engineering',
            f'- ("CI/CD pipeline" OR "software delivery platform" OR "engineering platform") {geo_ind}',
            f'- ("Snyk" OR "Checkmarx" OR "Veracode" OR "Semgrep" OR "CodeQL") {geo_ind}',
        ])

        secure_sdlc_queries = "\n".join([
            f'- ("secure SDLC" OR "shift-left security" OR "secure coding") {geo_ind}',
            f'- ("static analysis" OR "SAST" OR "code scanning") {geo_ind}',
            f'- ("software assurance" OR "secure by design" OR "DevSecOps adoption") {geo_ind}',
            f'- ("software supply chain security" OR "supply chain attack prevention") {geo_ind}',
            f'- ("quality gate" OR "code quality initiative") {geo_ind} engineering',
            f'- ("application security program" OR "AppSec maturity") {geo_ind}',
        ])

        engineering_scale_queries = "\n".join([
            f'- ("developer productivity" OR "engineering efficiency") {geo_ind}',
            f'- ("legacy modernization" OR "core system replacement" OR "platform consolidation") {geo_ind}',
            f'- ("internal developer platform" OR "release automation" OR "engineering acceleration") {geo_ind}',
            f'- ("software factory" OR "engineering center of excellence") {geo_ind}',
            f'- ("scaling engineering" OR "growing engineering team" OR "hiring developers") {geo_ind}',
        ])

        return (
            f"**1. Hiring signal searches (last 90 days):**\n{hiring_queries}\n\n"
            f"**2. News signal searches (last 90 days):**\n{news_queries}\n\n"
            f"**3. Tech stack / CI-CD signal searches:**\n{tech_stack_queries}\n\n"
            f"**4. Secure SDLC / AppSec signal searches:**\n{secure_sdlc_queries}\n\n"
            f"**5. Engineering scale / modernisation signal searches:**\n{engineering_scale_queries}\n"
        )

    # ── Response parsing ──────────────────────────────────────────────────────

    def _parse_response(
        self,
        text: str,
        countries: list[str],
        industries: list[str],
    ) -> tuple[list[dict], list[str]]:
        data = self._safe_json_loads(text)
        limitations: list[str] = []

        if not isinstance(data, dict):
            return [], ["Could not parse discovery response as JSON."]

        raw = data.get("companies", [])
        if not isinstance(raw, list):
            return [], ["Discovery response had unexpected format."]

        limitations.extend(
            str(lim) for lim in data.get("limitations", [])
            if isinstance(lim, str)
        )

        accounts: list[dict] = []
        seen_domains: set[str] = set()
        seen_companies: set[str] = set()

        for item in raw:
            if not isinstance(item, dict):
                continue

            company = str(item.get("company", "")).strip()
            domain = str(item.get("domain", "")).strip()

            # Reject entries missing company or domain
            if not company or not domain:
                continue

            # Normalise domain — strip protocol/path
            domain = re.sub(r"^https?://", "", domain)
            domain = domain.split("/")[0].lower().removeprefix("www.")

            # Dedupe by domain first, then by company name
            if domain and domain in seen_domains:
                continue
            if company.lower() in seen_companies:
                continue
            if domain:
                seen_domains.add(domain)
            seen_companies.add(company.lower())

            country = str(item.get("country", countries[0] if countries else "")).strip()
            industry = str(item.get("industry", industries[0] if industries else "")).strip()

            trigger = str(item.get("trigger_signal", "")).strip().lower()
            if trigger not in _VALID_TRIGGER_SIGNALS:
                trigger = "web_search_result"

            confidence = str(item.get("confidence", "")).strip()
            if confidence not in _VALID_CONFIDENCE:
                confidence = "Low"

            source_url = str(item.get("source_url", "")).strip()
            # Reject obviously non-URL values
            if source_url and not source_url.startswith("http"):
                source_url = ""

            accounts.append({
                "company": company,
                "domain": domain,
                "country": country,
                "industry": industry,
                "trigger_signal": trigger,
                "signal_summary": str(item.get("signal_summary", "")).strip(),
                "source_type": str(item.get("source_type", "web_search_result")).strip(),
                "source_url": source_url,
                "signal_date": str(item.get("signal_date", "")).strip(),
                "confidence": confidence,
            })

        if not accounts:
            limitations.append(
                "Discovery agent found no companies matching the criteria. "
                "Try broader country or industry inputs."
            )

        return accounts, limitations

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _safe_json_loads(self, text: str) -> dict:
        text = text.strip()
        text = re.sub(r"```(?:json)?", "", text).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

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
