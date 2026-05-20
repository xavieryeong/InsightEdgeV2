from __future__ import annotations

"""
ClaudeNewsSearchTool — uses Claude API with web_search_20250305 to discover
recent Sonar-relevant news about a target company.

Python fetches and validates all returned URLs before creating evidence.
Claude must not invent URLs or findings.
"""

import re
import json
import anthropic

from agents.base import safe_create
from agents.common.models import SearchResult
from config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL

_MAX_SEARCH_ITERATIONS = 6
_MAX_RESULTS = 10


class ClaudeNewsSearchTool:

    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or ANTHROPIC_API_KEY
        self._client = anthropic.Anthropic(api_key=key) if key else None
        self.model = model or CLAUDE_MODEL

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    # ── Public interface ──────────────────────────────────────────────────────

    def search(
        self, company: str, domain: str = "",
    ) -> tuple[list[SearchResult], list[str], dict]:
        """Return ``(results, limitations, usage)``."""
        limitations: list[str] = []
        usage = {"input": 0, "output": 0}

        if not self._client:
            limitations.append(
                "Claude news search is not configured because ANTHROPIC_API_KEY is missing."
            )
            return [], limitations, usage

        prompt = self._build_prompt(company, domain)

        try:
            raw_text, loop_limitations = self._run_with_web_search(prompt, usage)
            limitations.extend(loop_limitations)
        except Exception as e:
            limitations.append(f"Claude news search API error: {e}")
            return [], limitations, usage

        if not raw_text:
            limitations.append("Claude news search returned no usable response.")
            return [], limitations, usage

        results, parse_limitations = self._parse_response(raw_text)
        limitations.extend(parse_limitations)

        if not results:
            limitations.append(
                f"Claude news search found no relevant articles for '{company}'."
            )

        return results, limitations, usage

    # ── Prompt ────────────────────────────────────────────────────────────────

    def _build_prompt(self, company: str, domain: str) -> str:
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=90)).strftime("%Y-%m-%d")
        domain_hint = f"The company domain is: {domain}" if domain else ""
        return f"""
You are a news discovery assistant for a sales intelligence tool.
You are searching for technology and engineering news relevant to Sonar, a code quality and application security company.

Target company: {company}
{domain_hint}

Use web search to find recent THIRD-PARTY news coverage about {company} published after {cutoff} (last 90 days only).
Only include technology, engineering, or security signals. Ignore sports, HR, CSR, general finance, and marketing news.

Run ALL of the following searches:
1. "{company}" cybersecurity OR "data breach" OR breach OR vulnerability OR ransomware OR "cyberattack" OR hacked
2. "{company}" "cloud migration" OR "digital transformation" OR "AI initiative" OR "generative AI" OR "AI platform" OR "AI strategy"
3. "{company}" "platform engineering" OR "engineering transformation" OR "cloud-native" OR DevOps OR MLOps OR "CI/CD"
4. "{company}" launches OR "new platform" OR "major release" OR "general availability" OR "developer platform" OR "product launch"
5. "{company}" new CTO OR new CISO OR "VP Engineering" OR "Chief Technology Officer" OR "Head of Platform" OR appoints
6. "{company}" "engineering center" OR "R&D expansion" OR "engineering hiring" OR "scaling engineering" OR "development center"

After searching, return ONLY valid JSON in this exact format with no markdown fences:

{{
  "results": [
    {{
      "title": "article headline",
      "url": "https://...",
      "snippet": "relevant text from the article",
      "source_type": "claude_web_search_result",
      "relevance_reason": "one sentence explaining why this is relevant for Sonar sales"
    }}
  ],
  "limitations": ["any issues or caveats with the search"]
}}

Rules:
- Only return real URLs you found through web search. Do not invent URLs.
- STRONGLY prefer third-party news sources (Reuters, Bloomberg, TechCrunch, The Register, ZDNet, Wired, Forbes, industry media) over the company's own press releases.
- Only include articles published in the last 90 days (after {cutoff}). Discard older articles.
- Only include technology or engineering signals — no sports, CSR, general financial, marketing, or unrelated HR news.
- Prioritize: cybersecurity incidents, cloud/AI transformation, product/platform launches, engineering investment, tech leadership changes.
- Do not claim an event occurred unless it appears in the search result text.
- Return at most {_MAX_RESULTS} high-quality results from diverse sources.
- Return empty results list if no relevant news found in the last 90 days.
""".strip()

    # ── Agentic web search loop ───────────────────────────────────────────────

    def _run_with_web_search(self, prompt: str, usage: dict) -> tuple[str, list[str]]:
        """
        Agentic loop for web_search_20250305.
        This tool is server-side: Anthropic executes the search automatically.
        The client continues the loop by acknowledging tool_use with empty content.
        Mutates the caller-provided ``usage`` dict with running token totals.
        """
        messages = [{"role": "user", "content": prompt}]
        tools = [{"type": "web_search_20250305", "name": "web_search"}]
        limitations: list[str] = []

        for iteration in range(_MAX_SEARCH_ITERATIONS):
            response = safe_create(
                self._client,
                model=self.model,
                max_tokens=4096,
                tools=tools,
                messages=messages,
            )
            usage["input"] += response.usage.input_tokens
            usage["output"] += response.usage.output_tokens

            text_output = "\n".join(
                b.text for b in response.content
                if hasattr(b, "type") and b.type == "text"
            )

            if response.stop_reason == "end_turn":
                return text_output, limitations

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": b.id, "content": ""}
                        for b in response.content
                        if hasattr(b, "type") and b.type == "tool_use"
                    ],
                })
                continue

            limitations.append(
                f"Claude news search stopped at iteration {iteration}: {response.stop_reason}"
            )
            if text_output:
                return text_output, limitations
            return "", limitations

        limitations.append("Claude news search reached maximum iterations.")
        return "", limitations

    # ── Parse Claude's JSON response ──────────────────────────────────────────

    def _safe_json_loads(self, text: str) -> dict:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {}

    def _parse_response(self, text: str) -> tuple[list[SearchResult], list[str]]:
        parsed = self._safe_json_loads(text)
        limitations = []

        if not parsed:
            return [], ["Could not parse Claude news search response as JSON."]

        raw_results = parsed.get("results", [])
        if not isinstance(raw_results, list):
            return [], ["Claude news search response had unexpected format."]

        results: list[SearchResult] = []
        for item in raw_results[:_MAX_RESULTS]:
            if not isinstance(item, dict):
                continue
            url = item.get("url", "").strip()
            title = item.get("title", "").strip()
            if not url or not url.startswith("http"):
                continue
            results.append(SearchResult(
                title=title,
                url=url,
                snippet=str(item.get("snippet", ""))[:500],
                source_type="claude_web_search_result",
                relevance_reason=str(item.get("relevance_reason", "")),
            ))

        limitations.extend(
            str(lim) for lim in parsed.get("limitations", [])
            if isinstance(lim, str)
        )

        return results, limitations
