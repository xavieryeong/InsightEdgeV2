from __future__ import annotations

"""
PublicNewsAgent — collects Sonar-relevant public news signals for a company.

3-layer discovery:
  1. Google News RSS  (dated items, company-relevance filtered)
  2. Company newsroom / IR page  (date extraction attempted from HTML)
  3. Claude web search fallback  (each URL fetched, validated, dated)

Python extracts, validates, and scores all evidence. Claude writes summary only.
"""

import re
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from agents.base import BaseAgent
from agents.news.config import (
    PRIMARY_WINDOW_DAYS,
    RECENCY_BONUS_DAYS,
    WEAK_EVIDENCE_THRESHOLD,
    NEWS_PATHS,
    URGENCY_KEYWORD_GROUPS,
    SCORING,
)
from agents.news.claude_news_search import ClaudeNewsSearchTool

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SalesAgent/1.0)"}
_FETCH_TIMEOUT = 10
_MAX_IR_HEADINGS = 30
_MAX_RSS_ITEMS = 25
_PROMPT_PATH = Path(__file__).parent / "prompt.md"

_COMPANY_SUFFIXES = frozenset({
    "inc", "corp", "corporation", "ltd", "limited", "llc", "llp",
    "plc", "ag", "sa", "nv", "bv", "gmbh", "co", "company",
    "group", "holdings", "holding", "bank", "technologies", "technology",
    "solutions", "services", "systems", "software", "digital",
    "international", "global", "enterprises", "ventures",
})

# Regex patterns for finding dates in plain text near headings
_ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_US_DATE_RE = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},?\s+20\d{2}\b",
    re.IGNORECASE,
)


class PublicNewsAgent(BaseAgent):

    def __init__(self):
        super().__init__()
        self._claude_search = ClaudeNewsSearchTool()

    # ── Entry point ───────────────────────────────────────────────────────────

    def run(
        self,
        company: str,
        domain: str = "",
        country: str = "",
        industry: str = "",
    ) -> dict:
        now = datetime.now(timezone.utc)
        all_evidence: list[dict] = []
        sources_checked: list[dict] = []
        limitations: list[str] = []
        usage = {"input": 0, "output": 0}

        # Layer 1: Google News RSS
        rss_ev, rss_src, rss_lim = self._fetch_google_news_rss(company, domain, now)
        all_evidence.extend(rss_ev)
        sources_checked.extend(rss_src)
        limitations.extend(rss_lim)

        # Layer 2: Company newsroom / IR page
        if domain:
            ir_ev, ir_src, ir_lim = self._fetch_company_news_page(domain, now)
            all_evidence.extend(ir_ev)
            sources_checked.extend(ir_src)
            limitations.extend(ir_lim)

        # Assign sequential IDs to initial evidence
        for i, ev in enumerate(all_evidence):
            ev["id"] = f"news_{i + 1:03d}"

        window_used = "90_days"
        window_days = PRIMARY_WINDOW_DAYS

        # Mark counted_in_score for initial evidence — undated items (days_ago < 0) never count
        for ev in all_evidence:
            ev["counted_in_score"] = 0 <= ev["days_ago"] <= window_days

        counted_initial = sum(1 for e in all_evidence if e["counted_in_score"])

        # Layer 3: Claude web search fallback (fetch + validate each URL)
        if counted_initial < WEAK_EVIDENCE_THRESHOLD and self._claude_search.is_configured:
            claude_ev, claude_src, claude_lim, claude_usage = self._fetch_claude_search_evidence(
                company, domain, window_days, now
            )
            all_evidence.extend(claude_ev)
            sources_checked.extend(claude_src)
            limitations.extend(claude_lim)
            usage["input"] += claude_usage["input"]
            usage["output"] += claude_usage["output"]

        # Drop evidence older than 90 days (undated items pass through)
        all_evidence = [
            e for e in all_evidence
            if e.get("days_ago", -1) < 0 or e.get("days_ago", -1) <= PRIMARY_WINDOW_DAYS
        ]

        # Final renumber after all layers
        for i, ev in enumerate(all_evidence):
            ev["id"] = f"news_{i + 1:03d}"

        counted_evidence = [e for e in all_evidence if e["counted_in_score"]]
        score, breakdown = self._calculate_score(counted_evidence, all_evidence)
        confidence = self._determine_confidence(counted_evidence)
        status = self._determine_status(counted_evidence, all_evidence)

        # Claude interpretation
        if all_evidence:
            try:
                interp, interp_usage = self._ask_claude_interpret(
                    company, all_evidence, score, breakdown, window_used
                )
                usage["input"] += interp_usage["input"]
                usage["output"] += interp_usage["output"]
            except Exception as e:
                limitations.append(f"Claude interpretation error: {e}")
                interp = {
                    "summary": "Unable to generate news summary.",
                    "sonar_relevance_reason": "",
                    "limitations": [],
                }
        else:
            interp = {
                "summary": "No public news evidence found for this company.",
                "sonar_relevance_reason": "No urgency signals detected in public news.",
                "limitations": ["No news sources returned usable content."],
            }
        limitations.extend(interp.get("limitations", []))

        # Write per-article summaries back onto evidence items
        article_summaries = interp.get("article_summaries", {})
        if article_summaries:
            for ev in all_evidence:
                s = article_summaries.get(ev["id"], "")
                if s:
                    ev["article_summary"] = s

        detected_categories = list({
            cat
            for e in counted_evidence
            for cat in [e["signal_type"]] + e.get("all_categories", [])
        })

        return {
            "company": company,
            "domain": domain,
            "signal": "public_news",
            "status": status,
            "window_used": window_used,
            "detected_categories": detected_categories,
            "evidence": all_evidence,
            "sonar_relevance_score": score,
            "score_breakdown": breakdown,
            "sonar_relevance_reason": interp.get("sonar_relevance_reason", ""),
            "summary": interp.get("summary", ""),
            "confidence": confidence,
            "limitations": limitations,
            "sources_checked": sources_checked,
            "_usage": usage,
        }

    # ── Layer 1: Google News RSS ──────────────────────────────────────────────

    def _fetch_google_news_rss(
        self, company: str, domain: str, now: datetime
    ) -> tuple[list, list, list]:
        evidence, sources_checked, limitations = [], [], []

        cq = f'"{company}"' if " " in company else company

        # Tech-focused queries — only signals relevant to Sonar (engineering/security)
        targeted_queries = [
            f"{cq} (cybersecurity OR breach OR vulnerability OR hacked OR ransomware OR \"data leak\" OR CVE)",
            f"{cq} (\"cloud migration\" OR \"digital transformation\" OR \"AI initiative\" OR \"generative AI\" OR DevOps OR MLOps)",
            f"{cq} (\"platform engineering\" OR \"engineering transformation\" OR \"cloud-native\" OR \"SaaS migration\")",
            f"{cq} (launches OR \"major release\" OR \"new platform\" OR \"general availability\" OR \"developer platform\")",
            f"{cq} (new CTO OR new CISO OR \"VP Engineering\" OR \"Chief Technology Officer\" OR appoints)",
        ]

        seen_urls: set[str] = set()
        for query in targeted_queries:
            rss_url = (
                f"https://news.google.com/rss/search"
                f"?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
            )
            sources_checked.append({
                "url": rss_url,
                "source_type": "google_news_rss",
                "fetch_status": "attempted",
            })
            try:
                resp = requests.get(rss_url, headers=_HEADERS, timeout=_FETCH_TIMEOUT)
                if resp.status_code != 200:
                    sources_checked[-1]["fetch_status"] = f"http_{resp.status_code}"
                    continue
                sources_checked[-1]["fetch_status"] = "success"
                for ev in self._parse_rss(resp.text, company, domain, now):
                    if ev["url"] not in seen_urls:
                        seen_urls.add(ev["url"])
                        evidence.append(ev)
            except Exception as e:
                sources_checked[-1]["fetch_status"] = "error"
                limitations.append(f"Google News RSS error: {e}")

        return evidence, sources_checked, limitations

    def _parse_rss(
        self, xml_text: str, company: str, domain: str, now: datetime
    ) -> list[dict]:
        evidence = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return evidence

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
                ).get_text(" ", strip=True)[:600]

            text_to_check = title + " " + description

            # Reject items not about this company (Google News can return tangential results)
            if not self._is_company_relevant(text_to_check, company, domain):
                continue

            categories = self._detect_urgency_categories(text_to_check)
            if not categories:
                continue

            days_ago, pub_date_iso = self._parse_rfc2822_date(pub_date_str, now)

            evidence.append({
                "id": "",
                "signal_type": categories[0],
                "all_categories": categories,
                "source_type": "google_news_rss",
                "title": title,
                "url": link,
                "snippet": description,
                "published_date": pub_date_iso,
                "days_ago": days_ago,
                "confidence": "High" if days_ago >= 0 else "Medium",
                "counted_in_score": False,
            })

        return evidence

    # ── Layer 2: Company newsroom / IR page ───────────────────────────────────

    def _fetch_company_news_page(
        self, domain: str, now: datetime
    ) -> tuple[list, list, list]:
        evidence, sources_checked, limitations = [], [], []
        base_url = self._build_base_url(domain)

        for path in NEWS_PATHS:
            url = f"{base_url}{path}"
            sources_checked.append({
                "url": url,
                "source_type": "company_news_page",
                "fetch_status": "attempted",
            })
            try:
                resp = requests.get(
                    url, headers=_HEADERS, timeout=_FETCH_TIMEOUT, allow_redirects=True
                )
                if resp.status_code == 200:
                    sources_checked[-1]["fetch_status"] = "success"
                    items = self._parse_news_page(resp.text, url, now)
                    evidence.extend(items)
                    if items:
                        break
                elif resp.status_code == 404:
                    sources_checked[-1]["fetch_status"] = "not_found"
                else:
                    sources_checked[-1]["fetch_status"] = f"http_{resp.status_code}"
            except Exception as e:
                sources_checked[-1]["fetch_status"] = "error"
                limitations.append(f"News page error ({url}): {e}")

        return evidence, sources_checked, limitations

    def _parse_news_page(self, html: str, url: str, now: datetime) -> list[dict]:
        evidence = []
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Page-level date (may apply to single-article pages)
        page_days_ago, page_date_iso = self._extract_meta_date(soup, now)

        for tag in soup.find_all(["h1", "h2", "h3"]):
            text = tag.get_text(" ", strip=True)
            if not (15 < len(text) < 300):
                continue

            categories = self._detect_urgency_categories(text)
            if not categories:
                continue

            # Try to find a date near this heading element
            days_ago, date_iso = self._extract_date_near_element(tag, now)

            # Fall back to page-level meta date
            if days_ago < 0 and page_days_ago >= 0:
                days_ago, date_iso = page_days_ago, page_date_iso

            evidence.append({
                "id": "",
                "signal_type": categories[0],
                "all_categories": categories,
                "source_type": "company_news_page",
                "title": text,
                "url": url,
                "snippet": "",
                "published_date": date_iso,
                "days_ago": days_ago,
                "confidence": "Medium" if days_ago >= 0 else "Low",
                "counted_in_score": False,
            })

        return evidence

    # ── Layer 3: Claude web search ────────────────────────────────────────────

    def _fetch_claude_search_evidence(
        self, company: str, domain: str, window_days: int, now: datetime
    ) -> tuple[list, list, list, dict]:
        evidence, sources_checked, limitations = [], [], []

        search_results, search_limitations, usage = self._claude_search.search(company, domain)
        limitations.extend(search_limitations)

        for i, result in enumerate(search_results):
            sources_checked.append({
                "url": result.url,
                "source_type": "claude_web_search",
                "fetch_status": "attempted",
            })

            validated = self._fetch_and_validate_url(result.url, company, domain, now)

            if validated:
                sources_checked[-1]["fetch_status"] = "success"
                categories = validated["categories"]
                title = validated["title"] or result.title
                snippet = validated["snippet"]
                days_ago = validated["days_ago"]
                date_iso = validated["published_date"]
                confidence = "Medium"
                counted = 0 <= days_ago <= window_days
            else:
                sources_checked[-1]["fetch_status"] = "fetch_failed"
                # Keep as Low confidence snippet; never counted without date validation
                categories = self._detect_urgency_categories(
                    result.title + " " + result.snippet
                )
                if not categories:
                    continue
                title = result.title
                snippet = result.snippet[:600]
                days_ago = -1
                date_iso = ""
                confidence = "Low"
                counted = False

            evidence.append({
                "id": f"cs_{i + 1:03d}",  # renumbered globally after all layers
                "signal_type": categories[0],
                "all_categories": categories,
                "source_type": "claude_web_search",
                "title": title,
                "url": result.url,
                "snippet": snippet,
                "published_date": date_iso,
                "days_ago": days_ago,
                "confidence": confidence,
                "counted_in_score": counted,
            })

        return evidence, sources_checked, limitations, usage

    def _fetch_and_validate_url(
        self, url: str, company: str, domain: str, now: datetime
    ) -> dict | None:
        """Fetch a URL, validate company relevance and urgency, extract date.
        Returns None if fetch fails or validation does not pass."""
        try:
            resp = requests.get(
                url, headers=_HEADERS, timeout=_FETCH_TIMEOUT, allow_redirects=True
            )
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")

            title_tag = soup.find("title")
            title_text = title_tag.get_text(strip=True) if title_tag else ""

            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            body_text = soup.get_text(" ", strip=True)[:3000]

            full_text = title_text + " " + body_text

            if not self._is_company_relevant(full_text, company, domain):
                return None

            # Scan article lead for urgency; limit to first 1500 chars to reduce noise
            categories = self._detect_urgency_categories(full_text[:1500])
            if not categories:
                return None

            days_ago, date_iso = self._extract_meta_date(soup, now)

            # Last resort: try to extract date from the URL itself
            if days_ago < 0:
                days_ago, date_iso = self._extract_date_from_url(url, now)

            return {
                "categories": categories,
                "title": title_text[:200],
                "snippet": body_text[:600],
                "published_date": date_iso,
                "days_ago": days_ago,
            }
        except Exception:
            return None

    # ── Urgency detection ─────────────────────────────────────────────────────

    def _detect_urgency_categories(self, text: str) -> list[str]:
        text_lower = text.lower()
        found = []
        for category, keywords in URGENCY_KEYWORD_GROUPS.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    found.append(category)
                    break
        return found

    # ── Company relevance ─────────────────────────────────────────────────────

    def _company_tokens(self, company: str) -> list[str]:
        tokens = re.split(r"[\s\-&,./]+", company.lower())
        return [t for t in tokens if t and t not in _COMPANY_SUFFIXES and len(t) > 2]

    def _is_company_relevant(self, text: str, company: str, domain: str) -> bool:
        text_lower = text.lower()
        if company.lower() in text_lower:
            return True
        if domain:
            base = domain.split(".")[0].lower()
            if len(base) > 2 and base in text_lower:
                return True
        for token in self._company_tokens(company):
            if len(token) > 3 and token in text_lower:
                return True
        return False

    # ── URL builder ───────────────────────────────────────────────────────────

    def _build_base_url(self, domain: str) -> str:
        if domain.startswith("http://") or domain.startswith("https://"):
            return domain.rstrip("/")
        return f"https://{domain}"

    # ── Date extraction ───────────────────────────────────────────────────────

    def _parse_rfc2822_date(self, date_str: str, now: datetime) -> tuple[int, str]:
        """Parse RFC 2822 date string (RSS pubDate format)."""
        if not date_str:
            return -1, ""
        try:
            dt = parsedate_to_datetime(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max((now - dt).days, 0), dt.strftime("%Y-%m-%d")
        except Exception:
            return self._flexible_parse(date_str, now)

    def _flexible_parse(self, text: str, now: datetime) -> tuple[int, str]:
        """Flexible date parse via dateutil. Returns (-1, '') on failure."""
        if not text:
            return -1, ""
        try:
            dt = dateutil_parser.parse(text, fuzzy=True)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            days_ago = max((now - dt).days, 0)
            if days_ago > 3650:  # reject implausibly old dates
                return -1, ""
            return days_ago, dt.strftime("%Y-%m-%d")
        except Exception:
            return -1, ""

    def _extract_meta_date(self, soup: BeautifulSoup, now: datetime) -> tuple[int, str]:
        """Extract date from HTML meta tags, JSON-LD, <time> elements, and body text."""
        # Meta tag candidates — property= and name= variants
        _META_ATTRS = [
            {"property": "article:published_time"},
            {"property": "article:modified_time"},
            {"property": "og:published_time"},
            {"property": "og:updated_time"},
            {"name": "date"},
            {"name": "pubdate"},
            {"name": "publish-date"},
            {"name": "publication_date"},
            {"name": "date-published"},
            {"name": "article.published"},
            {"name": "timestamp"},
            {"name": "DC.date"},
            {"name": "DC.Date"},
            {"itemprop": "datePublished"},
            {"itemprop": "dateModified"},
        ]
        for attrs in _META_ATTRS:
            tag = soup.find("meta", attrs)
            if tag:
                result = self._flexible_parse(tag.get("content", ""), now)
                if result[0] >= 0:
                    return result

        # JSON-LD structured data (NewsArticle, Article, BlogPosting)
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    data = data[0] if data else {}
                for key in ("datePublished", "dateModified", "dateCreated"):
                    val = data.get(key, "")
                    if val:
                        result = self._flexible_parse(str(val), now)
                        if result[0] >= 0:
                            return result
            except Exception:
                pass

        # <time> elements with datetime attribute
        for time_tag in soup.find_all("time", attrs={"datetime": True}):
            result = self._flexible_parse(time_tag["datetime"], now)
            if result[0] >= 0:
                return result

        # URL embedded in canonical link (e.g. /news/2025/04/23/title)
        canonical = soup.find("link", {"rel": "canonical"})
        if canonical:
            result = self._extract_date_from_url(canonical.get("href", ""), now)
            if result[0] >= 0:
                return result

        # Scan visible body text for ISO or US date patterns
        body_text = soup.get_text(" ", strip=True)[:2000]
        for pattern in [_ISO_DATE_RE, _US_DATE_RE]:
            match = pattern.search(body_text)
            if match:
                result = self._flexible_parse(match.group(0), now)
                if result[0] >= 0:
                    return result

        return -1, ""

    def _extract_date_from_url(self, url: str, now: datetime) -> tuple[int, str]:
        """Extract date from URL path segments like /2025/04/23/ or /2025-04-23/."""
        _URL_DATE_RE = re.compile(r"/(20\d{2})[/\-](\d{2})[/\-](\d{2})")
        match = _URL_DATE_RE.search(url)
        if match:
            date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
            return self._flexible_parse(date_str, now)
        return -1, ""

    def _extract_date_near_element(self, element, now: datetime) -> tuple[int, str]:
        """Try to find a date near the given heading element — checks siblings and grandparent."""
        # Walk up to grandparent and check time tags + sibling text
        scopes = [element]
        parent = element.parent
        if parent:
            scopes.append(parent)
            if parent.parent:
                scopes.append(parent.parent)

        for scope in scopes:
            if scope is None:
                continue
            for time_tag in scope.find_all("time"):
                dt_str = time_tag.get("datetime") or time_tag.get_text(strip=True)
                result = self._flexible_parse(dt_str, now)
                if result[0] >= 0:
                    return result

        # Scan text in up to grandparent scope for date patterns
        for scope in scopes[1:]:
            if scope is None:
                continue
            scope_text = scope.get_text(" ", strip=True)
            for pattern in [_ISO_DATE_RE, _US_DATE_RE]:
                match = pattern.search(scope_text)
                if match:
                    result = self._flexible_parse(match.group(0), now)
                    if result[0] >= 0:
                        return result

        return -1, ""

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _calculate_score(
        self, counted_evidence: list[dict], all_evidence: list[dict]
    ) -> tuple[float, dict]:
        if not counted_evidence:
            return 0.0, {"total": 0.0}

        detected: set[str] = set()
        for e in counted_evidence:
            detected.add(e["signal_type"])
            for c in e.get("all_categories", []):
                detected.add(c)

        breakdown: dict = {}
        total = 0.0
        for category in [
            "cybersecurity_incident", "cloud_ai_transformation",
            "product_platform_launch", "engineering_investment", "leadership_change",
        ]:
            if category in detected:
                pts = SCORING[category]
                breakdown[category] = pts
                total += pts

        has_recent = any(0 <= e["days_ago"] <= RECENCY_BONUS_DAYS for e in all_evidence)
        if has_recent and breakdown:
            breakdown["recency_bonus"] = SCORING["recency_bonus"]
            total += SCORING["recency_bonus"]

        total = min(total, SCORING["total_cap"])
        breakdown["total"] = round(total, 1)
        return round(total, 1), breakdown

    # ── Confidence / status ───────────────────────────────────────────────────

    def _determine_confidence(self, counted_evidence: list[dict]) -> str:
        if not counted_evidence:
            return "Low"
        high_count = sum(1 for e in counted_evidence if e["confidence"] == "High")
        if high_count >= 2:
            return "High"
        if high_count >= 1:
            return "Medium"
        return "Low"

    def _determine_status(
        self, counted_evidence: list[dict], all_evidence: list[dict]
    ) -> str:
        if counted_evidence:
            return "completed"
        if all_evidence:
            return "partial"
        return "no_data"

    # ── Claude interpretation ─────────────────────────────────────────────────

    def _ask_claude_interpret(
        self,
        company: str,
        evidence: list[dict],
        score: float,
        breakdown: dict,
        window_used: str,
    ) -> tuple[dict, dict]:
        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

        ev_summary = [
            {
                "id": e["id"],
                "signal_type": e["signal_type"],
                "title": e["title"],
                "snippet": e["snippet"][:400] if e["snippet"] else "",
                "published_date": e["published_date"],
                "days_ago": e["days_ago"],
                "confidence": e["confidence"],
                "counted_in_score": e["counted_in_score"],
            }
            for e in evidence[:15]
        ]

        user_message = (
            f"Company: {company}\n"
            f"Window used: {window_used}\n"
            f"Sonar Relevance Score: {score}\n"
            f"Score breakdown:\n{json.dumps(breakdown, indent=2)}\n\n"
            f"Evidence ({len(ev_summary)} items):\n{json.dumps(ev_summary, indent=2)}\n\n"
            "Return JSON with exactly four fields: summary, sonar_relevance_reason, "
            "limitations, article_summaries.\n"
            "article_summaries must be an object mapping each evidence id to a single "
            "clean sentence (max 25 words) describing what actually happened in that article. "
            "Write factual, specific sentences — not generic descriptions. "
            "Only include items where counted_in_score is true. "
            "Example: {\"news_001\": \"Siemens confirmed attackers accessed its GitHub Actions "
            "pipeline, exposing CI credentials across three product teams.\"}"
        )

        raw, usage = self.ask_claude(system_prompt, user_message)
        return self._safe_json_loads(raw), usage

    def _safe_json_loads(self, text: str) -> dict:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                except json.JSONDecodeError:
                    return {}
            else:
                return {}

        if not isinstance(parsed.get("summary"), str):
            parsed["summary"] = str(parsed.get("summary", ""))
        if not isinstance(parsed.get("sonar_relevance_reason"), str):
            parsed["sonar_relevance_reason"] = str(parsed.get("sonar_relevance_reason", ""))
        if not isinstance(parsed.get("limitations"), list):
            parsed["limitations"] = []
        if not isinstance(parsed.get("article_summaries"), dict):
            parsed["article_summaries"] = {}

        return parsed
