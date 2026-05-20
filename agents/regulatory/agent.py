from __future__ import annotations

"""
RegulatoryImpactAgent — ENT only.

3-layer discovery:
  1. Google News RSS  (4 regulatory-targeted queries, keyword-filtered)
  2. Company compliance / trust / privacy pages  (heading extraction)
  3. Claude (no web search) — uses training knowledge + Python evidence
     to assess applicable regulations, score, and return JSON.
"""

import json
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from agents.base import BaseAgent, safe_create
from agents.regulatory.config import (
    SCORE_CAPS,
    TOTAL_SCORE_CAP,
    VALID_SCORE_CATEGORIES,
    VALID_STATUSES,
    VALID_CONFIDENCE,
)
from config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL  # noqa: F401

_PROMPT_PATH = Path(__file__).parent / "prompt.md"
_FETCH_TIMEOUT = 10
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SalesAgent/1.0)"}

# Paths to try for company compliance / trust / press release pages
_COMPLIANCE_PATHS = [
    "/compliance",
    "/security",
    "/trust",
    "/trust-center",
    "/security-center",
    "/privacy",
    "/legal/privacy",
    "/newsroom",
    "/press",
    "/press-releases",
    "/media/press-releases",
    "/about/compliance",
    "/about/security",
    "/cybersecurity",
    "/governance",
    "/certifications",
]

# Keywords that flag a headline or page heading as regulatory-relevant
_REGULATORY_KEYWORDS = [
    "compliance", "regulatory", "gdpr", "fine", "audit", "enforcement",
    "pci dss", "hipaa", "iso 27001", "soc 2", "nis2", "dora", "misra",
    "fedramp", "breach", "penalty", "investigation", "settlement",
    "cybersecurity requirement",
]

# RSS items to inspect per query (cap to keep runtime reasonable)
_MAX_RSS_ITEMS = 25


class RegulatoryImpactAgent(BaseAgent):

    def run(
        self,
        company: str,
        domain: str = "",
        country: str = "",
        industry: str = "",
    ) -> dict:
        if not ANTHROPIC_API_KEY:
            return self._safe_fallback(
                company, domain,
                "ANTHROPIC_API_KEY is not configured",
            )

        # ── Layer 1: Google News RSS ──────────────────────────────────────────
        rss_evidence, _, rss_limitations = self._fetch_rss(company)

        # ── Layer 2: Company compliance pages ────────────────────────────────
        page_evidence, _, page_limitations = (
            self._fetch_compliance_pages(domain) if domain else ([], [], [])
        )

        pre_evidence = rss_evidence + page_evidence
        limitations_pre = rss_limitations + page_limitations

        # ── Layer 3: Claude web search with pre-found context ────────────────
        system_prompt, user_message = self._build_prompt(
            company, domain, country, industry, pre_evidence
        )

        try:
            response = safe_create(
                self.client,
                model=self.model,
                max_tokens=8192,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            raw_text = response.content[0].text
            usage = {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
            }
        except Exception as e:
            return self._safe_fallback(
                company, domain, f"Regulatory research API error: {e}"
            )

        if not raw_text:
            return self._safe_fallback(
                company, domain,
                "Regulatory research returned no usable response",
                usage=usage,
            )

        print(f"[REG DEBUG] raw_text length={len(raw_text)}")
        print(f"[REG DEBUG] raw_text[:800]:\n{raw_text[:800]}\n---")

        result = self._parse_response(raw_text)
        if result is None:
            return self._safe_fallback(
                company, domain,
                "Could not parse regulatory research response as JSON. "
                f"Raw response (first 500 chars): {raw_text[:500]}",
                usage=usage,
            )

        result["company"] = company
        result["domain"] = domain

        if limitations_pre:
            result.setdefault("limitations", [])
            result["limitations"].extend(limitations_pre)

        # Debug: if score is still 0 after parsing, surface evidence count so user can see why
        if result.get("sonar_relevance_score", 0) == 0:
            ev_count = len(result.get("evidence", []))
            counted = sum(
                1 for e in result.get("evidence", []) if e.get("counted_in_score")
            )
            result.setdefault("limitations", [])
            result["limitations"].append(
                f"[Debug] Score=0 after parsing. Evidence items: {ev_count}, "
                f"counted_in_score=True: {counted}. "
                f"Raw response (first 600 chars): {raw_text[:600]}"
            )

        result["_usage"] = usage
        return result

    # ── Layer 1: Google News RSS ──────────────────────────────────────────────

    def _fetch_rss(
        self, company: str
    ) -> tuple[list[dict], list[dict], list[str]]:
        evidence: list[dict] = []
        sources: list[dict] = []
        limitations: list[str] = []

        cq = f'"{company}"' if " " in company else company

        queries = [
            f'{cq} (GDPR OR "data protection" OR "regulatory fine" OR compliance OR audit)',
            f'{cq} (PCI DSS OR HIPAA OR "ISO 27001" OR "SOC 2" OR NIS2 OR DORA)',
            f'{cq} (enforcement OR investigation OR settlement OR lawsuit OR "regulatory action")',
            f'{cq} ("data breach" OR "security incident" OR cybersecurity) regulatory',
        ]

        seen_urls: set[str] = set()
        now = datetime.now(timezone.utc)

        for query in queries:
            rss_url = (
                f"https://news.google.com/rss/search"
                f"?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
            )
            src_entry: dict = {
                "url": rss_url,
                "source_type": "google_news_rss",
                "status": "attempted",
                "notes": "",
            }
            sources.append(src_entry)
            try:
                resp = requests.get(rss_url, headers=_HEADERS, timeout=_FETCH_TIMEOUT)
                if resp.status_code != 200:
                    src_entry["status"] = f"http_{resp.status_code}"
                    continue
                src_entry["status"] = "fetched"
                for item in self._parse_rss_items(resp.text, now):
                    if item["source_url"] not in seen_urls:
                        seen_urls.add(item["source_url"])
                        evidence.append(item)
            except Exception as e:
                src_entry["status"] = "error"
                limitations.append(f"Regulatory RSS error for query '{query[:60]}': {e}")

        return evidence, sources, limitations

    def _parse_rss_items(self, xml_text: str, now: datetime) -> list[dict]:
        items: list[dict] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return items

        for item in root.findall(".//item")[:_MAX_RSS_ITEMS]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date_str = (item.findtext("pubDate") or "").strip()
            description = (item.findtext("description") or "").strip()

            if not title or not link:
                continue

            if description:
                description = BeautifulSoup(
                    description, "html.parser"
                ).get_text(" ", strip=True)[:300]

            combined = (title + " " + description).lower()

            # Only keep items with at least one regulatory keyword
            if not any(kw in combined for kw in _REGULATORY_KEYWORDS):
                continue

            published_date, days_ago = self._parse_rfc2822(pub_date_str, now)

            items.append({
                "layer": "rss",
                "title": title,
                "source_url": link,
                "snippet": description,
                "published_date": published_date,
                "days_ago": days_ago,
            })

        return items

    # ── Layer 2: Company compliance / trust / privacy pages ───────────────────

    def _fetch_compliance_pages(
        self, domain: str
    ) -> tuple[list[dict], list[dict], list[str]]:
        evidence: list[dict] = []
        sources: list[dict] = []
        limitations: list[str] = []

        # Step 1: Use Google to search for the company's own compliance/trust pages
        discovered_urls = self._discover_compliance_urls(domain)

        # Step 2: Also try fixed generic paths
        base = domain if domain.startswith("http") else f"https://{domain}"
        base = base.rstrip("/")
        fixed_urls = [f"{base}{path}" for path in _COMPLIANCE_PATHS]

        all_urls = list(dict.fromkeys(discovered_urls + fixed_urls))  # dedup, discovery first

        for url in all_urls[:8]:  # cap total fetches
            src_entry: dict = {"url": url, "source_type": "company_compliance_page",
                               "status": "attempted", "notes": ""}
            sources.append(src_entry)
            try:
                resp = requests.get(url, headers=_HEADERS, timeout=_FETCH_TIMEOUT,
                                    allow_redirects=True)
                if resp.status_code == 404:
                    src_entry["status"] = "not_found"
                    continue
                if resp.status_code != 200:
                    src_entry["status"] = f"http_{resp.status_code}"
                    continue

                src_entry["status"] = "fetched"
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()

                # Extract headings AND body paragraphs mentioning regulatory keywords
                snippets: list[str] = []
                for el in soup.find_all(["h1", "h2", "h3", "p", "li"]):
                    text = el.get_text(" ", strip=True)
                    if not text or len(text) < 20:
                        continue
                    if any(kw in text.lower() for kw in _REGULATORY_KEYWORDS):
                        snippets.append(text[:300])
                    if len(snippets) >= 15:
                        break

                if snippets:
                    evidence.append({
                        "layer": "company_page",
                        "source_url": url,
                        "headings": snippets,
                    })

            except Exception as e:
                src_entry["status"] = "error"
                limitations.append(f"Compliance page error ({url}): {e}")

        return evidence, sources, limitations

    def _discover_compliance_urls(self, domain: str) -> list[str]:
        """Use Google News RSS to find the company's actual compliance/trust pages."""
        query = f'site:{domain} (compliance OR certification OR cybersecurity OR "ISO 27001" OR "SOC 2" OR trust OR GDPR)'
        rss_search = (
            f"https://news.google.com/rss/search"
            f"?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        )
        urls: list[str] = []
        try:
            resp = requests.get(rss_search, headers=_HEADERS, timeout=_FETCH_TIMEOUT)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                for item in root.findall(".//item")[:5]:
                    link = (item.findtext("link") or "").strip()
                    # Only keep links from the company's own domain
                    if link and domain in link:
                        urls.append(link)
        except Exception:
            pass
        return urls

    # ── Prompt builder ────────────────────────────────────────────────────────

    def _build_prompt(
        self,
        company: str,
        domain: str,
        country: str,
        industry: str,
        pre_evidence: list[dict],
    ) -> tuple[str, str]:
        """Returns (system_prompt, user_message) for ask_claude."""
        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

        # Format pre-evidence as plain bullet list
        if pre_evidence:
            bullets = []
            for ev in pre_evidence[:8]:
                if ev.get("layer") == "rss":
                    date = f" ({ev['published_date']})" if ev.get("published_date") else ""
                    bullets.append(
                        f"- [NEWS{date}] {ev.get('title', '')} | {ev.get('source_url', '')}"
                    )
                elif ev.get("layer") == "company_page":
                    headings = "; ".join(ev.get("headings", [])[:3])
                    bullets.append(f"- [COMPANY PAGE] {ev.get('source_url', '')} — {headings}")
            pre_ev_text = "\n".join(bullets) if bullets else "None found by Python scraping."
        else:
            pre_ev_text = "None found by Python scraping."

        user_message = (
            "## Target Company\n\n"
            f"Company: {company}\n"
            f"Domain: {domain or 'not provided'}\n"
            f"Country/Market: {country or 'detect from your knowledge'}\n"
            f"Industry: {industry or 'detect from your knowledge'}\n\n"
            "## Pre-found Evidence (Python scraping)\n\n"
            "The following signals were scraped by Python before you were invoked:\n\n"
            f"{pre_ev_text}\n\n"
            "## Instructions\n\n"
            f"Research {company}'s regulatory situation using your training knowledge. "
            "Specifically:\n\n"
            f"1. Check what you know from {company}'s own website ({domain}), "
            "including their trust center, cybersecurity governance pages, press releases, "
            "newsroom, and annual reports — for any certifications (ISO 27001, SOC 2, TISAX, "
            "PCI DSS, HIPAA, etc.) they hold or compliance programs they participate in.\n\n"
            f"2. Check what you know from {company}'s press releases and public announcements "
            "about compliance, security certifications, audits, or regulatory actions.\n\n"
            "3. Based on their industry and country, identify which regulations apply to them "
            "that are directly relevant to SOFTWARE SECURITY, CODE QUALITY, SECURE SDLC, "
            "APPLICATION SECURITY, or CYBERSECURITY compliance — these are the only areas "
            "where Sonar provides value.\n\n"
            "SCOPE RULES — only include these regulation types:\n"
            "- Cybersecurity laws and directives (NIS2, DORA, IT-Sicherheitsgesetz, KRITIS)\n"
            "- Software coding standards (MISRA C/C++, ISO 26262, DO-178C, IEC 62443)\n"
            "- Information security certifications (ISO 27001, SOC 2, FedRAMP, CMMC)\n"
            "- Payment/data security standards only if the company is a payment processor "
            "(PCI DSS, HIPAA)\n"
            "- Active enforcement actions related to cybersecurity or software security\n"
            "- Regulator guidance specifically about secure software development\n\n"
            "DO NOT INCLUDE — exclude these entirely, they are not relevant to Sonar:\n"
            "- Tax compliance, financial reporting regulations, securities law (SEBI, SEC, etc.)\n"
            "- Employment law, HR compliance, labour regulations\n"
            "- General financial regulations unless they explicitly mandate secure SDLC\n"
            "- GDPR unless there is direct evidence of a code-related data breach or enforcement\n"
            "- Duplicate entries for the same regulation (e.g. NIS2 and IT-Sicherheitsgesetz "
            "are the same — pick one)\n"
            "- Generic industry overviews that list multiple regulations without a specific finding\n\n"
            "DATE RULE — only include evidence from 2024 or 2025. Do NOT reference compliance "
            "events, certifications achieved, or regulatory actions from before January 2024. "
            "If a certification or regulation has been in place since before 2024 but is still "
            "active today, you may include it but note it as 'ongoing' rather than citing "
            "the original date.\n\n"
            "4. For each regulation or certification, create an evidence item with:\n"
            "   - source_url: REQUIRED — provide a real URL the user can open to verify this "
            "finding. Use the company's own website (trust center, governance page, press release, "
            "annual report), an official regulator page, or a credible news article. "
            "Only leave source_url as empty string for pure industry-mapping items where no "
            "specific verifiable URL exists (set source_type: 'industry_mapping' in that case).\n"
            "   - source_type: 'company_website' | 'official_regulator_website' | "
            "'public_news' | 'industry_mapping'\n"
            "   - counted_in_score: true for all evidence you are confident about\n"
            "   - confidence: 'High' if from company website or official regulator page, "
            "'Medium' if from press/news, 'Low' if inferred from industry only\n\n"
            "IMPORTANT: Prefer evidence items you can attach a real source_url to. "
            "Do NOT create evidence items with empty source_url unless the source_type is "
            "'industry_mapping'. Every company_website, official_regulator_website, and "
            "public_news evidence item must have a populated source_url.\n\n"
            "CRITICAL: Return ONLY valid JSON. No markdown fences, no text before or after the JSON."
        )

        return system_prompt, user_message

    # ── Response parsing and validation ──────────────────────────────────────

    def _parse_response(self, text: str) -> dict | None:
        data = self._safe_json_loads(text)
        if not isinstance(data, dict) or not data:
            return None

        # Required string fields
        for field in (
            "industry_detected", "country_detected", "regulator_checked",
            "regulator_website", "summary", "sonar_relevance_reason",
            "recommended_sales_angle",
        ):
            if not isinstance(data.get(field), str):
                data[field] = ""

        data["signal"] = "regulatory_impact"

        if data.get("status") not in VALID_STATUSES:
            data["status"] = "partial"

        if data.get("confidence") not in VALID_CONFIDENCE:
            data["confidence"] = "Low"

        # List fields
        for field in (
            "applicable_regulations", "detected_categories",
            "evidence", "limitations", "sources_checked",
        ):
            if not isinstance(data.get(field), list):
                data[field] = []

        # Validate and clamp score_breakdown
        breakdown = data.get("score_breakdown")
        if not isinstance(breakdown, dict):
            breakdown = {}
        for cat in VALID_SCORE_CATEGORIES:
            try:
                breakdown[cat] = min(float(breakdown.get(cat, 0)), SCORE_CAPS[cat])
            except (TypeError, ValueError):
                breakdown[cat] = 0.0
        breakdown["total"] = min(
            sum(breakdown[cat] for cat in VALID_SCORE_CATEGORIES),
            TOTAL_SCORE_CAP,
        )
        data["score_breakdown"] = breakdown

        # Validate evidence items (must happen before score enforcement below)
        valid_evidence = []
        for i, item in enumerate(data["evidence"]):
            if not isinstance(item, dict):
                continue
            item.setdefault("id", f"reg_{i + 1:03d}")
            item.setdefault("type", "general_regulatory_mention")
            item.setdefault("value", "")
            item.setdefault("source_type", "claude_web_search_result")
            item.setdefault("source_url", "")
            item.setdefault("evidence_text", "")
            item.setdefault("regulation", "")
            item.setdefault("regulator", "")
            item.setdefault("country", "")
            item.setdefault("industry", "")
            item.setdefault("confidence", "Low")
            # Accept bool true OR string "true"/"yes" — Claude sometimes returns strings.
            counted = item.get("counted_in_score")
            if isinstance(counted, bool):
                item["counted_in_score"] = counted
            elif isinstance(counted, str) and counted.lower() in ("true", "yes", "1"):
                item["counted_in_score"] = True
            else:
                item["counted_in_score"] = False
            valid_evidence.append(item)
        data["evidence"] = valid_evidence

        # Enforce evidence-backed scoring: zero out any category with no supporting evidence.
        # Exception: industry_mapping evidence is always counted (it represents valid
        # industry knowledge); categories supported only by industry_mapping are capped at 3.0.
        supported_direct = {
            item["type"]
            for item in valid_evidence
            if item.get("counted_in_score") is True
            and item.get("source_type") != "industry_mapping"
        }
        supported_mapping = {
            item["type"]
            for item in valid_evidence
            if item.get("source_type") == "industry_mapping"
        }
        mapping_only_total = 0.0
        for cat in VALID_SCORE_CATEGORIES:
            if breakdown[cat] > 0:
                if cat in supported_direct:
                    pass  # full score allowed
                elif cat in supported_mapping:
                    mapping_only_total += breakdown[cat]
                else:
                    breakdown[cat] = 0.0  # no evidence at all — zero out
        # Cap the portion supported only by industry_mapping at 3.0
        if mapping_only_total > 3.0:
            ratio = 3.0 / mapping_only_total
            for cat in VALID_SCORE_CATEGORIES:
                if cat not in supported_direct and cat in supported_mapping and breakdown[cat] > 0:
                    breakdown[cat] = round(breakdown[cat] * ratio, 2)
        breakdown["total"] = min(
            sum(breakdown[cat] for cat in VALID_SCORE_CATEGORIES),
            TOTAL_SCORE_CAP,
        )
        data["score_breakdown"] = breakdown
        data["sonar_relevance_score"] = breakdown["total"]

        # Validate sources_checked items
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

    def _parse_rfc2822(self, date_str: str, now: datetime) -> tuple[str, int]:
        """Parse an RSS pubDate string. Returns (ISO date string, days_ago)."""
        if not date_str:
            return "", -1
        try:
            dt = parsedate_to_datetime(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            days_ago = max((now - dt).days, 0)
            return dt.strftime("%Y-%m-%d"), days_ago
        except Exception:
            pass
        # Fallback: dateutil flexible parse
        try:
            dt = dateutil_parser.parse(date_str, fuzzy=True)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            days_ago = max((now - dt).days, 0)
            if days_ago > 3650:
                return "", -1
            return dt.strftime("%Y-%m-%d"), days_ago
        except Exception:
            return "", -1

    def _safe_json_loads(self, text: str) -> dict:
        text = text.strip()
        # Strip markdown fences anywhere in the text
        text = re.sub(r"```(?:json)?", "", text).strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Use brace-counting to extract the first complete JSON object
        # (more reliable than greedy regex when there's prose before/after)
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
            "signal": "regulatory_impact",
            "status": "error",
            "industry_detected": "",
            "country_detected": "",
            "regulator_checked": "",
            "regulator_website": "",
            "applicable_regulations": [],
            "detected_categories": [],
            "sonar_relevance_score": 0,
            "score_breakdown": {
                "active_fine_lawsuit": 0.0,
                "specific_regulation_applies": 0.0,
                "compliance_audit": 0.0,
                "regulated_industry": 0.0,
                "regional_regulator_relevance": 0.0,
                "general_regulatory_mention": 0.0,
                "total": 0.0,
            },
            "summary": "",
            "sonar_relevance_reason": "",
            "recommended_sales_angle": "",
            "confidence": "Low",
            "evidence": [],
            "limitations": [reason],
            "sources_checked": [],
            "_usage": usage or {"input": 0, "output": 0},
        }
