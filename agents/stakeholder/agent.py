from __future__ import annotations

"""
StakeholderIntelligenceAgent — ENT only.

Claude API with web_search identifies key technical decision-makers and infers
their personality colour energy (Insights Discovery 4-colour model) from public
signals: LinkedIn posts, speeches, events, articles.

Python: builds prompt, runs agentic loop, validates JSON, returns fallback.
Claude: does all research and personality inference.

Anti-hallucination:
- Stakeholder omitted if no name found in public source.
- LinkedIn URL only returned if found via search (never constructed).
- Personality set to Unknown/None with Low confidence if no signals found.
- Personality is probabilistic — flagged as inference, not ground truth.
"""

import json
import re
from pathlib import Path

from agents.base import BaseAgent, safe_create
from agents.stakeholder.config import (
    VALID_STATUSES,
    VALID_CONFIDENCE,
    VALID_PRIMARY_COLOURS,
    VALID_SECONDARY_COLOURS,
)
from config.settings import ANTHROPIC_API_KEY  # noqa: F401

_PROMPT_PATH = Path(__file__).parent / "prompt.md"
_MAX_SEARCH_ITERATIONS = 12


class StakeholderIntelligenceAgent(BaseAgent):

    def run(self, company: str, domain: str = "") -> dict:
        if not ANTHROPIC_API_KEY:
            return self._safe_fallback(
                company, domain, "ANTHROPIC_API_KEY is not configured"
            )

        prompt = self._build_prompt(company, domain)

        try:
            raw_text, loop_limitations, usage = self._run_with_web_search(prompt)
        except Exception as e:
            return self._safe_fallback(
                company, domain, f"Stakeholder research API error: {e}"
            )

        if not raw_text:
            return self._safe_fallback(
                company, domain,
                "Stakeholder research returned no usable response",
                usage=usage,
            )

        result = self._parse_response(raw_text)
        if result is None:
            return self._safe_fallback(
                company, domain,
                "Could not parse stakeholder research response as JSON",
                usage=usage,
            )

        result["company"] = company
        result["domain"] = domain

        if loop_limitations:
            result.setdefault("limitations", [])
            result["limitations"].extend(loop_limitations)

        result["_usage"] = usage
        return result

    # ── Prompt ────────────────────────────────────────────────────────────────

    def _build_prompt(self, company: str, domain: str) -> str:
        instructions = _PROMPT_PATH.read_text(encoding="utf-8")
        domain_line = (
            f"Domain: {domain}" if domain
            else "Domain: Not provided — search for the company website"
        )
        return (
            f"{instructions}\n\n"
            "---\n\n"
            "## Target Company\n\n"
            f"Company: {company}\n"
            f"{domain_line}\n\n"
            "Research this company's technical leadership now and return the JSON."
        )

    # ── Agentic web search loop ───────────────────────────────────────────────

    def _run_with_web_search(self, prompt: str) -> tuple[str, list[str], dict]:
        """
        Agentic loop for web_search_20250305.
        Server-side: Anthropic executes searches automatically.
        Client acknowledges tool_use with empty tool_result content.
        Returns ``(text, limitations, usage)``.
        """
        messages = [{"role": "user", "content": prompt}]
        tools = [{"type": "web_search_20250305", "name": "web_search"}]
        limitations: list[str] = []
        usage = {"input": 0, "output": 0}

        for iteration in range(_MAX_SEARCH_ITERATIONS):
            response = safe_create(
                self.client,
                model=self.model,
                max_tokens=8192,
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
                return text_output, limitations, usage

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
                f"Stakeholder search stopped at iteration {iteration}: "
                f"{response.stop_reason}"
            )
            if text_output:
                return text_output, limitations, usage
            return "", limitations, usage

        limitations.append("Stakeholder search reached maximum iterations.")
        return "", limitations, usage

    # ── Response parsing and validation ──────────────────────────────────────

    def _parse_response(self, text: str) -> dict | None:
        data = self._safe_json_loads(text)
        if not isinstance(data, dict) or not data:
            return None

        data["signal"] = "stakeholder_intelligence"

        if data.get("status") not in VALID_STATUSES:
            data["status"] = "partial"

        if data.get("confidence") not in VALID_CONFIDENCE:
            data["confidence"] = "Low"

        if not isinstance(data.get("limitations"), list):
            data["limitations"] = []

        # Validate each stakeholder
        valid_stakeholders = []
        for item in data.get("stakeholders", []):
            if not isinstance(item, dict):
                continue

            # Must have a name — omit if empty
            name = str(item.get("name", "")).strip()
            if not name:
                continue

            item["name"] = name
            item.setdefault("role", "")
            item.setdefault("linkedin_url", "")
            item.setdefault("confidence", "Low")
            item.setdefault("personality_signals", [])
            item.setdefault("personality_reasoning", "")
            item.setdefault("source_urls", [])

            # Validate confidence
            if item["confidence"] not in VALID_CONFIDENCE:
                item["confidence"] = "Low"

            # Validate and normalise LinkedIn URL
            linkedin = str(item.get("linkedin_url", "")).strip()
            if linkedin and not linkedin.startswith("https://"):
                linkedin = ""
            item["linkedin_url"] = linkedin

            # Validate colours
            primary = str(item.get("personality_primary", "Unknown")).strip()
            if primary not in VALID_PRIMARY_COLOURS:
                primary = "Unknown"
            item["personality_primary"] = primary

            secondary = str(item.get("personality_secondary", "None")).strip()
            if secondary not in VALID_SECONDARY_COLOURS:
                secondary = "None"
            # Secondary must differ from primary
            if secondary == primary:
                secondary = "None"
            item["personality_secondary"] = secondary

            # Recompute personality_display from validated values
            if primary == "Unknown" or secondary == "None":
                item["personality_display"] = primary
            else:
                item["personality_display"] = f"{primary}/{secondary}"

            # Ensure list fields are lists
            for list_field in ("personality_signals", "source_urls"):
                if not isinstance(item.get(list_field), list):
                    item[list_field] = []

            valid_stakeholders.append(item)

        data["stakeholders"] = valid_stakeholders

        # Validate sources_checked
        valid_sources = []
        for src in data.get("sources_checked", []):
            if not isinstance(src, dict):
                continue
            src.setdefault("url", "")
            src.setdefault("type", "")
            src.setdefault("status", "searched")
            src.setdefault("notes", "")
            valid_sources.append(src)
        data["sources_checked"] = valid_sources

        return data

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

    def _safe_fallback(
        self, company: str, domain: str, reason: str, usage: dict | None = None,
    ) -> dict:
        return {
            "company": company,
            "domain": domain,
            "signal": "stakeholder_intelligence",
            "status": "error",
            "stakeholders": [],
            "sources_checked": [],
            "limitations": [reason],
            "confidence": "Low",
            "_usage": usage or {"input": 0, "output": 0},
        }
