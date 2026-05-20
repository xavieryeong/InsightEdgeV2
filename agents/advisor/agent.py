from __future__ import annotations

import json
import re

from agents.base import BaseAgent
from agents.advisor.config import SYSTEM_PROMPT
from agents.director import (
    AGENT_TECH_STACK, AGENT_HIRING, AGENT_NEWS,
    AGENT_POSITION, AGENT_REGULATORY, AGENT_PROFILE,
    AGENT_STAKEHOLDER, AGENT_PAIN_POINTS,
)


class SignalAdvisorAgent(BaseAgent):

    def analyse(self, company: str, signals: dict) -> dict:
        summary = self._build_signal_summary(company, signals)
        prompt = f"""\
Analyse all researched signals for {company} and recommend the strongest outreach hook \
for Sonar sales.

{summary}

Decide whether to recommend a single signal or a combination. Only combine if the signals \
genuinely reinforce each other and make the hook more compelling. If one signal is already \
specific, urgent, and Sonar-relevant on its own, recommend that signal alone. Do not force \
a combination just because multiple signals exist.

Return JSON with exactly these fields:
{{
  "hook_title": "Specific, problem-led hook title that references this company's actual \
situation — not generic",
  "hook_rationale": "2–3 sentences explaining why this signal (or combination) is the \
strongest hook for Sonar outreach right now",
  "strategy_note": "Directive for the email writing agent: what tension to lead with, \
which signal is the primary hook, how Sonar specifically addresses this situation, and \
the core message in one sentence. Name the actual signals and findings.",
  "suggested_signals": [
    {{
      "type": "hiring|news|tech_stack|regulatory|pain_points",
      "label": "Short display label shown to the sales rep (max 60 chars)",
      "content": "Full content passed to the email agent — include what happened, when, \
specific details, snippet text if available, and why it matters to Sonar",
      "why": "One sentence: why this specific signal is compelling for Sonar outreach"
    }}
  ]
}}
"""
        try:
            raw, usage = self.ask_claude(SYSTEM_PROMPT, prompt)
            result = self._parse(raw)
            result["_usage"] = usage
            return result
        except Exception as e:
            return {
                "error": str(e),
                "hook_title": "", "hook_rationale": "",
                "strategy_note": "", "suggested_signals": [],
                "_usage": {"input": 0, "output": 0},
            }

    # ── Signal summary builder ────────────────────────────────────────────────

    def _build_signal_summary(self, company: str, signals: dict) -> str:
        lines = [f"Company: {company}\n"]

        # Company Profile
        profile = signals.get(AGENT_PROFILE, {})
        if profile and profile.get("snapshot"):
            snap = profile["snapshot"]
            lines.append("## Company Profile")
            for key, label in [
                ("what_they_do",     "What they do"),
                ("who_they_sell_to", "Customers"),
                ("business_model",   "Business model"),
                ("ai_posture",       "AI posture"),
            ]:
                val = snap.get(key, "")
                if val:
                    lines.append(f"  {label}: {val}")

        # Company Position
        pos = signals.get(AGENT_POSITION, {})
        if pos:
            lines.append("\n## Company Position")
            lines.append(f"  Label: {pos.get('position_label', '—')}")
            summary = pos.get("summary", "")
            if summary:
                lines.append(f"  Summary: {summary[:400]}")

        # Tech Stack
        ts = signals.get(AGENT_TECH_STACK, {})
        if ts:
            lines.append(
                f"\n## Tech Stack  (Sonar relevance score: {ts.get('sonar_relevance_score', 0)}/10)"
            )
            for cat, items in [
                ("Languages",      ts.get("languages", [])),
                ("CI/CD tools",    ts.get("cicd_tools", [])),
                ("Cloud / DevOps", ts.get("cloud", [])),
                ("Security tools", ts.get("security_tools", [])),
            ]:
                if items:
                    names = ", ".join(i.get("name", "") for i in items)
                    lines.append(f"  {cat}: {names}")

        # Hiring Signals
        hiring = signals.get(AGENT_HIRING, {})
        if hiring:
            lines.append(
                f"\n## Hiring Signals  (Sonar relevance score: {hiring.get('sonar_relevance_score', 0)}/10)"
            )
            if hiring.get("summary"):
                lines.append(f"  Summary: {hiring['summary']}")
            evidence = [e for e in hiring.get("evidence", []) if e.get("counted_in_score")]
            for e in evidence[:6]:
                lines.append(
                    f"  - Role: {e.get('value', '—')} | Category: {e.get('type', '')} | "
                    f"Source: {e.get('source_url', '')}"
                )

        # Public News
        news = signals.get(AGENT_NEWS, {})
        if news:
            lines.append(
                f"\n## Public News  (Sonar relevance score: {news.get('sonar_relevance_score', 0)}/10)"
            )
            if news.get("summary"):
                lines.append(f"  Summary: {news['summary']}")
            evidence = [e for e in news.get("evidence", []) if e.get("counted_in_score")]
            for e in evidence[:5]:
                snippet = e.get("snippet", "")[:400]
                lines.append(
                    f"  - [{e.get('published_date', '?')}] {e.get('title', '')} | "
                    f"Signal type: {e.get('signal_type', '')} | "
                    f"Snippet: {snippet} | URL: {e.get('url', '')}"
                )

        # Regulatory Impact
        reg = signals.get(AGENT_REGULATORY, {})
        if reg:
            lines.append(
                f"\n## Regulatory Impact  (Sonar relevance score: {round(reg.get('sonar_relevance_score', 0), 2)}/10)"
            )
            evidence = (
                [e for e in reg.get("evidence", []) if e.get("counted_in_score")]
                or reg.get("evidence", [])
            )
            for e in evidence[:4]:
                lines.append(
                    f"  - Regulation: {e.get('regulation', '—')} | "
                    f"Finding: {e.get('evidence_text', '')[:300]} | "
                    f"Source: {e.get('source_url', '')}"
                )

        # Developer Pain Points (Velocity)
        pain = signals.get(AGENT_PAIN_POINTS, {})
        if pain:
            lines.append(
                f"\n## Developer Pain Points  (Sonar relevance score: {pain.get('sonar_relevance_score', 0)}/10)"
            )
            if pain.get("summary"):
                lines.append(f"  Summary: {pain['summary']}")
            if pain.get("recommended_sales_angle"):
                lines.append(f"  Recommended angle: {pain['recommended_sales_angle']}")
            evidence = [e for e in pain.get("evidence", []) if e.get("counted_in_score")]
            for e in evidence[:4]:
                lines.append(
                    f"  - [{e.get('category', '')}] {e.get('evidence_text', '')[:300]}"
                )

        # Stakeholders (context only — not a signal, but useful for framing)
        sk = signals.get(AGENT_STAKEHOLDER, {})
        if sk and sk.get("stakeholders"):
            lines.append("\n## Key Stakeholders")
            for p in sk["stakeholders"][:3]:
                lines.append(
                    f"  - {p.get('name', '—')} | {p.get('role', '—')} | "
                    f"Personality: {p.get('personality_display', '—')}"
                )

        return "\n".join(lines)

    # ── JSON parser ───────────────────────────────────────────────────────────

    def _parse(self, text: str) -> dict:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "hook_title" in data:
                return data
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    pass
        return {
            "error": "Could not parse advisor response",
            "hook_title": "", "hook_rationale": "",
            "strategy_note": "", "suggested_signals": [],
        }
