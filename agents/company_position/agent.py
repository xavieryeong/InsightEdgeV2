from __future__ import annotations

"""
CompanyPositionAgent — classifies a company as AI Leader, Skeptic, or Laggard.

Synthesises outputs from TechStackAgent, HiringPatternAgent, and PublicNewsAgent.
Python calculates all dimension scores and the classification label.
Claude writes the summary, classification reason, sales angle, and limitations only.

Anti-hallucination: every dimension score must trace to input evidence.
Missing inputs score 0 for that dimension — never inferred from company name or size.
"""

import json
import re
from pathlib import Path

from agents.base import BaseAgent
from agents.company_position.config import (
    LEADER_THRESHOLD,
    LAGGARD_THRESHOLD,
    SKEPTIC_DOMINANT_COUNT,
    AI_INNOVATION_LEADER_KEYWORDS,
    SKEPTIC_FLAG_KEYWORDS,
    LEADERSHIP_LEADER_KEYWORDS,
    LEADERSHIP_SKEPTIC_KEYWORDS,
    LEADER_HIRING_CATEGORIES,
    SKEPTIC_HIRING_CATEGORIES,
    NEWS_AI_LEADER_CATEGORIES,
    NEWS_LEADERSHIP_CATEGORIES,
)

_PROMPT_PATH = Path(__file__).parent / "prompt.md"


class CompanyPositionAgent(BaseAgent):

    def run(
        self,
        company: str,
        tech_stack_result: dict | None = None,
        hiring_result: dict | None = None,
        news_result: dict | None = None,
        extra_evidence: list[dict] | None = None,
    ) -> dict:
        extra_evidence = extra_evidence or []

        # ── Step 1: Extract normalized evidence from all inputs ───────────────
        raw_evidence: list[dict] = []
        raw_evidence.extend(self._extract_tech_stack_evidence(tech_stack_result or {}))
        raw_evidence.extend(self._extract_hiring_evidence(hiring_result or {}))
        raw_evidence.extend(self._extract_news_evidence(news_result or {}))
        for ev in extra_evidence:
            raw_evidence.append({
                "source_signal": "extra",
                "dimension": str(ev.get("dimension", "ai_innovation_news")),
                "evidence_text": str(ev.get("evidence_text", "")),
                "source_url": str(ev.get("source_url", "")),
                "confidence": str(ev.get("confidence", "Low")),
                "supports": str(ev.get("supports", "leader")),
            })
        for i, ev in enumerate(raw_evidence):
            ev["id"] = f"pos_{i + 1:03d}"

        # ── Step 2: Score each dimension (Python only) ────────────────────────
        dim_scores = {
            "ai_innovation_news": self._score_ai_innovation_news(
                news_result, raw_evidence
            ),
            "hiring_signals": self._score_hiring_signals(hiring_result),
            "tech_stack_maturity": self._score_tech_stack_maturity(tech_stack_result),
            "engineering_visibility": self._score_engineering_visibility(
                tech_stack_result
            ),
            "leadership_messaging": self._score_leadership_messaging(
                news_result, extra_evidence
            ),
        }

        # ── Step 3: Collect skeptic flags ─────────────────────────────────────
        skeptic_flags = self._collect_skeptic_flags(news_result, extra_evidence)

        # ── Step 4: Classify ──────────────────────────────────────────────────
        classification_score = sum(dim_scores.values())
        position_label, confidence = self._classify(
            dim_scores, skeptic_flags, len(raw_evidence)
        )

        # ── Step 5: Claude interpretation ─────────────────────────────────────
        usage = {"input": 0, "output": 0}
        if raw_evidence or classification_score > 0:
            try:
                interp, usage = self._ask_claude_interpret(
                    company,
                    raw_evidence,
                    dim_scores,
                    classification_score,
                    position_label,
                    confidence,
                    skeptic_flags,
                )
            except Exception as e:
                interp = {
                    "summary": "Unable to generate company position summary.",
                    "classification_reason": "",
                    "recommended_sales_angle": "",
                    "limitations": [f"Claude interpretation error: {e}"],
                }
        else:
            interp = {
                "summary": (
                    f"Insufficient public evidence to classify {company}'s "
                    "technology position."
                ),
                "classification_reason": (
                    "No meaningful evidence found across any dimension."
                ),
                "recommended_sales_angle": (
                    "Deprioritize unless compliance, regulatory, or security "
                    "incident triggers are identified."
                ),
                "limitations": [
                    "No agent results provided. Classification defaults to "
                    "Laggard with Low confidence."
                ],
            }

        return {
            "company": company,
            "signal": "company_position_focus",
            "position_label": position_label,
            "confidence": confidence,
            "classification_score": classification_score,
            "sonar_relevance_score": classification_score,
            "dimension_scores": dim_scores,
            "skeptic_flags": skeptic_flags,
            "evidence": raw_evidence,
            "summary": interp.get("summary", ""),
            "classification_reason": interp.get("classification_reason", ""),
            "recommended_sales_angle": interp.get("recommended_sales_angle", ""),
            "limitations": interp.get("limitations", []),
            "_usage": usage,
        }

    # ── Evidence extraction ───────────────────────────────────────────────────

    def _extract_tech_stack_evidence(self, result: dict) -> list[dict]:
        if not result or result.get("status") in ("error", "no_data"):
            return []

        evidence = []
        score = result.get("sonar_relevance_score", 0)

        cicd_items = result.get("cicd_tools", [])
        if cicd_items:
            tools = [i.get("name", "") for i in cicd_items[:4] if isinstance(i, dict)]
            evidence.append({
                "source_signal": "tech_stack",
                "dimension": "tech_stack_maturity",
                "evidence_text": f"CI/CD tooling detected: {', '.join(t for t in tools if t)}",
                "source_url": "",
                "confidence": "High",
                "supports": "leader",
            })

        cloud_items = result.get("cloud", [])
        if cloud_items:
            tools = [i.get("name", "") for i in cloud_items[:4] if isinstance(i, dict)]
            evidence.append({
                "source_signal": "tech_stack",
                "dimension": "tech_stack_maturity",
                "evidence_text": f"Cloud/DevOps tools detected: {', '.join(t for t in tools if t)}",
                "source_url": "",
                "confidence": "High",
                "supports": "leader",
            })

        lang_items = result.get("languages", [])
        if lang_items:
            lang_names = [i.get("name", "") for i in lang_items[:4] if isinstance(i, dict)]
            evidence.append({
                "source_signal": "tech_stack",
                "dimension": "tech_stack_maturity",
                "evidence_text": f"Programming languages identified: {', '.join(n for n in lang_names if n)}",
                "source_url": "",
                "confidence": "Medium",
                "supports": "leader",
            })

        # Engineering visibility — CI/CD presence implies public GitHub activity
        if cicd_items or score >= 3:
            evidence.append({
                "source_signal": "tech_stack",
                "dimension": "engineering_visibility",
                "evidence_text": "Public technical signals found (GitHub / public repos)",
                "source_url": "",
                "confidence": "Medium",
                "supports": "leader",
            })

        return evidence

    def _extract_hiring_evidence(self, result: dict) -> list[dict]:
        if not result or result.get("status") in ("error", "no_data"):
            return []

        categories = set(result.get("detected_categories", []))
        if not categories:
            return []

        evidence = []
        conf = result.get("confidence", "Medium")
        leader_cats = sorted(categories & LEADER_HIRING_CATEGORIES)
        skeptic_cats = sorted(categories & SKEPTIC_HIRING_CATEGORIES)

        if leader_cats:
            evidence.append({
                "source_signal": "hiring_patterns",
                "dimension": "hiring_signals",
                "evidence_text": f"Public job postings indicate roles in: {', '.join(leader_cats)}",
                "source_url": "",
                "confidence": conf,
                "supports": "leader",
            })

        if skeptic_cats and not leader_cats:
            evidence.append({
                "source_signal": "hiring_patterns",
                "dimension": "hiring_signals",
                "evidence_text": (
                    f"Hiring is focused on security/governance roles: "
                    f"{', '.join(skeptic_cats)} — risk-control emphasis"
                ),
                "source_url": "",
                "confidence": conf,
                "supports": "skeptic",
            })

        return evidence

    def _extract_news_evidence(self, result: dict) -> list[dict]:
        if not result or result.get("status") in ("error", "no_data"):
            return []

        evidence = []
        categories = result.get("detected_categories", [])
        conf = result.get("confidence", "Medium")

        # AI innovation dimension — from detected categories
        ai_leader_cats = [c for c in categories if c in NEWS_AI_LEADER_CATEGORIES]
        if ai_leader_cats:
            evidence.append({
                "source_signal": "public_news",
                "dimension": "ai_innovation_news",
                "evidence_text": f"News signals detected: {', '.join(ai_leader_cats)}",
                "source_url": "",
                "confidence": conf,
                "supports": "leader",
            })

        if "compliance_regulatory" in categories:
            evidence.append({
                "source_signal": "public_news",
                "dimension": "ai_innovation_news",
                "evidence_text": "Compliance or regulatory pressure signals in news",
                "source_url": "",
                "confidence": conf,
                "supports": "skeptic",
            })

        # Scan news evidence items for AI innovation and skeptic keyword matches
        found_leader_in_text = False
        found_skeptic_in_text = False

        for ev in result.get("evidence", [])[:5]:
            if not ev.get("counted_in_score"):
                continue
            title = ev.get("title", "")
            snippet = ev.get("snippet", "")
            text = (title + " " + snippet).lower()

            if not found_leader_in_text:
                for kw in AI_INNOVATION_LEADER_KEYWORDS:
                    if kw in text:
                        evidence.append({
                            "source_signal": "public_news",
                            "dimension": "ai_innovation_news",
                            "evidence_text": f'News: "{title[:100]}"',
                            "source_url": ev.get("url", ""),
                            "confidence": ev.get("confidence", "Medium"),
                            "supports": "leader",
                        })
                        found_leader_in_text = True
                        break

            if not found_skeptic_in_text:
                for kw in SKEPTIC_FLAG_KEYWORDS:
                    if kw in text:
                        evidence.append({
                            "source_signal": "public_news",
                            "dimension": "ai_innovation_news",
                            "evidence_text": f'Cautious AI messaging: "{title[:100]}"',
                            "source_url": ev.get("url", ""),
                            "confidence": ev.get("confidence", "Medium"),
                            "supports": "skeptic",
                        })
                        found_skeptic_in_text = True
                        break

        # Leadership dimension
        if "leadership_change" in categories:
            evidence.append({
                "source_signal": "public_news",
                "dimension": "leadership_messaging",
                "evidence_text": "Leadership change detected (new CTO / CISO / VP Engineering)",
                "source_url": "",
                "confidence": conf,
                "supports": "leader",
            })

        return evidence

    # ── Dimension scoring ─────────────────────────────────────────────────────

    def _score_ai_innovation_news(
        self, news_result: dict | None, evidence: list[dict]
    ) -> int:
        if not news_result:
            return 0

        categories = news_result.get("detected_categories", [])

        strong_leader = {
            "cloud_ai_transformation", "cloud_ai_initiative",  # current + legacy
        }
        moderate_leader = {
            "product_platform_launch", "product_launch", "acquisition",
            "engineering_investment", "cybersecurity_incident", "hiring_wave",
        }

        if any(c in categories for c in strong_leader):
            # Downgrade to 1 if skeptic evidence outnumbers leader evidence
            dim_ev = [e for e in evidence if e.get("dimension") == "ai_innovation_news"]
            skeptic_count = sum(1 for e in dim_ev if e.get("supports") == "skeptic")
            leader_count  = sum(1 for e in dim_ev if e.get("supports") == "leader")
            return 1 if skeptic_count > leader_count else 2

        if any(c in categories for c in moderate_leader):
            return 1

        return 0

    def _score_hiring_signals(self, hiring_result: dict | None) -> int:
        if not hiring_result:
            return 0

        categories = set(hiring_result.get("detected_categories", []))
        leader_cats = categories & LEADER_HIRING_CATEGORIES
        skeptic_cats = categories & SKEPTIC_HIRING_CATEGORIES

        if len(leader_cats) >= 3:
            return 2
        if len(leader_cats) >= 1:
            return 1
        if skeptic_cats:
            return 1  # hiring is risk/compliance-focused rather than innovation-focused

        return 0

    def _score_tech_stack_maturity(self, tech_stack_result: dict | None) -> int:
        if not tech_stack_result:
            return 0

        has_cicd  = bool(tech_stack_result.get("cicd_tools"))
        has_cloud = bool(tech_stack_result.get("cloud"))
        has_langs = bool(tech_stack_result.get("languages"))

        if has_cicd and has_cloud:
            return 2
        if has_cicd or has_cloud or has_langs:
            return 1

        return 0

    def _score_engineering_visibility(self, tech_stack_result: dict | None) -> int:
        if not tech_stack_result:
            return 0

        score     = tech_stack_result.get("sonar_relevance_score", 0)
        has_cicd  = bool(tech_stack_result.get("cicd_tools"))
        has_cloud = bool(tech_stack_result.get("cloud"))

        # CI/CD evidence implies public GitHub activity = public engineering presence
        if has_cicd and score >= 4:
            return 2
        if has_cicd or has_cloud or score >= 2:
            return 1

        return 0

    def _score_leadership_messaging(
        self,
        news_result: dict | None,
        extra_evidence: list[dict],
    ) -> int:
        all_text = ""
        categories: list[str] = []

        if news_result:
            categories = news_result.get("detected_categories", [])
            for ev in news_result.get("evidence", [])[:10]:
                all_text += " " + ev.get("title", "") + " " + ev.get("snippet", "")

        for ev in extra_evidence:
            all_text += " " + ev.get("evidence_text", "")

        all_text = all_text.lower()

        leader_hits = sum(1 for kw in LEADERSHIP_LEADER_KEYWORDS if kw in all_text)
        skeptic_hits = sum(1 for kw in LEADERSHIP_SKEPTIC_KEYWORDS if kw in all_text)

        has_leadership_change = "leadership_change" in categories

        if has_leadership_change and leader_hits >= 1:
            return 2
        if has_leadership_change:
            return 1  # new leader signal even if messaging stance is unclear

        if leader_hits >= 2:
            return 2
        if leader_hits >= 1:
            return 1
        if skeptic_hits >= 1:
            return 1  # risk/governance-focused leadership messaging

        return 0

    # ── Skeptic flag collection ───────────────────────────────────────────────

    def _collect_skeptic_flags(
        self,
        news_result: dict | None,
        extra_evidence: list[dict],
    ) -> list[str]:
        texts: list[str] = []

        if news_result:
            for ev in news_result.get("evidence", [])[:10]:
                texts.append(ev.get("title", "") + " " + ev.get("snippet", ""))

        for ev in extra_evidence:
            texts.append(ev.get("evidence_text", ""))

        combined = " ".join(texts).lower()
        return [kw for kw in SKEPTIC_FLAG_KEYWORDS if kw in combined]

    # ── Classification ────────────────────────────────────────────────────────

    def _classify(
        self,
        dim_scores: dict,
        skeptic_flags: list[str],
        evidence_count: int,
    ) -> tuple[str, str]:
        total = sum(dim_scores.values())

        has_strong_leader = any(
            dim_scores.get(dim, 0) == 2
            for dim in ("ai_innovation_news", "hiring_signals", "tech_stack_maturity")
        )
        skeptic_dominant = len(skeptic_flags) >= SKEPTIC_DOMINANT_COUNT
        has_any_skeptic = len(skeptic_flags) >= 1

        # Confidence based on evidence breadth
        active_dims = sum(1 for v in dim_scores.values() if v > 0)
        if evidence_count >= 4 and active_dims >= 3:
            confidence = "High"
        elif evidence_count >= 2 and active_dims >= 2:
            confidence = "Medium"
        else:
            confidence = "Low"

        # No evidence at all → Laggard with Low confidence immediately
        if evidence_count == 0 or total == 0:
            return "Laggard", "Low"

        # Tie-breaker: high score but dominant skeptic flags → Skeptic
        if total >= LEADER_THRESHOLD and skeptic_dominant:
            return "Skeptic", confidence

        # AI Leader: high score + strong signal + no dominant skeptic
        if total >= LEADER_THRESHOLD and has_strong_leader:
            return "AI Leader", confidence

        # Skeptic: dominant flags always win regardless of score
        if skeptic_dominant:
            return "Skeptic", confidence

        # Low score → Laggard
        if total <= LAGGARD_THRESHOLD:
            return "Laggard", "Low" if evidence_count < 2 else confidence

        # Medium range (4–6) with any skeptic flag → Skeptic
        if has_any_skeptic:
            return "Skeptic", confidence

        # Medium range with strong innovation signal → AI Leader (capped at Medium)
        if has_strong_leader:
            capped = "Medium" if confidence == "High" else confidence
            return "AI Leader", capped

        # Medium range, no strong signals, no skeptic flags → Skeptic by default
        return "Skeptic", confidence

    # ── Claude interpretation ─────────────────────────────────────────────────

    def _ask_claude_interpret(
        self,
        company: str,
        evidence: list[dict],
        dim_scores: dict,
        classification_score: int,
        position_label: str,
        confidence: str,
        skeptic_flags: list[str],
    ) -> tuple[dict, dict]:
        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

        ev_summary = [
            {
                "id": e["id"],
                "dimension": e["dimension"],
                "evidence_text": e["evidence_text"],
                "supports": e["supports"],
                "confidence": e["confidence"],
            }
            for e in evidence[:15]
        ]

        user_message = (
            f"Company: {company}\n"
            f"position_label: {position_label}\n"
            f"confidence: {confidence}\n"
            f"classification_score: {classification_score} / 10\n"
            f"dimension_scores:\n{json.dumps(dim_scores, indent=2)}\n"
            f"skeptic_flags: {json.dumps(skeptic_flags)}\n\n"
            f"Evidence ({len(ev_summary)} items):\n{json.dumps(ev_summary, indent=2)}\n\n"
            "Return JSON with exactly four fields: "
            "summary, classification_reason, recommended_sales_angle, limitations."
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

        for field in ("summary", "classification_reason", "recommended_sales_angle"):
            if not isinstance(parsed.get(field), str):
                parsed[field] = str(parsed.get(field, ""))
        if not isinstance(parsed.get("limitations"), list):
            parsed["limitations"] = []

        return parsed
