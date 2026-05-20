from __future__ import annotations

"""
CompanyProfileAgent — runs for both ENT and Velocity roles.

Claude API with web_search researches the company from public sources:
website, newsroom, investor relations, news, LinkedIn job postings.

Python: builds prompt, runs agentic loop, validates JSON shape, returns fallback.
Claude: does all research and produces the structured snapshot.
Anti-hallucination: Claude must not invent facts; empty string if not found.
"""

import json
import re
from pathlib import Path

from agents.base import BaseAgent, safe_create
from agents.company_profile.config import (
    VALID_STATUSES,
    VALID_CONFIDENCE,
    SNAPSHOT_FIELDS,
)
from config.settings import ANTHROPIC_API_KEY  # noqa: F401

_PROMPT_PATH = Path(__file__).parent / "prompt.md"
_MAX_SEARCH_ITERATIONS = 8


class CompanyProfileAgent(BaseAgent):

    def run(self, company: str, domain: str = "") -> dict:
        if not ANTHROPIC_API_KEY:
            return self._safe_fallback(
                company, domain, "ANTHROPIC_API_KEY is not configured"
            )

        prompt = self._build_prompt(company, domain)

        try:
            raw_text, loop_limitations, usage = self._run_with_web_search(prompt)
        except Exception as e:
            return self._safe_fallback(company, domain, f"Company profile API error: {e}")

        if not raw_text:
            return self._safe_fallback(
                company, domain, "Company profile research returned no usable response",
                usage=usage,
            )

        result = self._parse_response(raw_text)
        if result is None:
            return self._safe_fallback(
                company, domain, "Could not parse company profile response as JSON",
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
            "Research this company now and return the JSON profile."
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
                f"Company profile search stopped at iteration {iteration}: "
                f"{response.stop_reason}"
            )
            if text_output:
                return text_output, limitations, usage
            return "", limitations, usage

        limitations.append("Company profile search reached maximum iterations.")
        return "", limitations, usage

    # ── Response parsing ──────────────────────────────────────────────────────

    def _parse_response(self, text: str) -> dict | None:
        data = self._safe_json_loads(text)
        if not isinstance(data, dict) or not data:
            return None

        data["signal"] = "company_profile"

        if data.get("status") not in VALID_STATUSES:
            data["status"] = "partial"

        if data.get("confidence") not in VALID_CONFIDENCE:
            data["confidence"] = "Low"

        # Validate snapshot
        snapshot = data.get("snapshot")
        if not isinstance(snapshot, dict):
            snapshot = {}
        for field in SNAPSHOT_FIELDS:
            if not isinstance(snapshot.get(field), str):
                snapshot[field] = ""
        data["snapshot"] = snapshot

        # List fields
        if not isinstance(data.get("limitations"), list):
            data["limitations"] = []

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
            "signal": "company_profile",
            "status": "error",
            "snapshot": {field: "" for field in SNAPSHOT_FIELDS},
            "sources_checked": [],
            "limitations": [reason],
            "confidence": "Low",
            "_usage": usage or {"input": 0, "output": 0},
        }
