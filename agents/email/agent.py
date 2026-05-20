from __future__ import annotations
import json
import re
from agents.base import BaseAgent
from agents.email.config import SYSTEM_PROMPT, PERSONALITY_TONES, HOOK_QUALITY_RULES, MAX_BODY_LINES, build_tone_guidance


class EmailDraftAgent(BaseAgent):

    def draft(
        self,
        company: str,
        target_name: str,
        target_role: str,
        personality: str | list[str],
        selected_items: list[dict],
        company_context: dict,
        company_position: str = "—",
        avoid_hook: str = "",
        strategy_note: str = "",
    ) -> dict:
        personalities = personality if isinstance(personality, list) else [personality]
        tone = build_tone_guidance(personalities)
        prompt = self._build_prompt(
            company, target_name, target_role, tone,
            selected_items, company_context, company_position,
            avoid_hook=avoid_hook,
            strategy_note=strategy_note,
        )
        try:
            raw, _usage = self.ask_claude(SYSTEM_PROMPT, prompt)
            result = self._parse(raw)
            return self._check_length(result)
        except Exception as e:
            return {"subject": "", "body": "", "error": str(e)}

    def _build_prompt(
        self,
        company: str,
        target_name: str,
        target_role: str,
        tone: str,
        selected_items: list[dict],
        company_context: dict,
        company_position: str,
        avoid_hook: str = "",
        strategy_note: str = "",
    ) -> str:
        items_text = "\n".join(
            f"- [{item.get('type', 'signal').upper()}] {item.get('content', '')}"
            for item in selected_items
            if item.get("content")
        ) or "No signals selected."

        context_lines = []
        if company_context.get("what_they_do"):
            context_lines.append(f"What they do: {company_context['what_they_do']}")
        if company_context.get("ai_posture"):
            context_lines.append(f"AI posture: {company_context['ai_posture']}")
        context_text = "\n".join(context_lines) or "No profile data available."

        avoid_section = (
            f"\n## Do NOT reuse this hook\n{avoid_hook}\n"
            f"Choose a completely different angle from the signals provided.\n"
            if avoid_hook else ""
        )

        strategy_section = (
            f"\n## Outreach Suggest Direction — FOLLOW THIS EXACTLY\n"
            f"The Outreach Suggest agent has analysed all available intelligence and determined the "
            f"following hook strategy. Do NOT invent a different angle. Build the email "
            f"around this direction using the signal evidence below as supporting proof.\n\n"
            f"{strategy_note}\n"
            if strategy_note else ""
        )

        return f"""\
## Target
Company: {company}
Contact: {target_name}, {target_role}
Company position: {company_position}

## Company Context
{context_text}
{strategy_section}
## Signal Evidence
{items_text}

## Personality & Tone Guidance
{tone}

{HOOK_QUALITY_RULES}{avoid_section}
## Instructions
1. Read all signal evidence. Identify the SINGLE most compelling hook — most relevant \
to {target_name}'s role, personality, and current situation.
2. Write hook_title: a sharp, specific, commercial title for this hook (see quality rules above).
3. Write hook_summary: 2 sentences explaining why this hook matters to {target_name} \
specifically — what pressure or risk does it surface for them?
4. Write the email opening around the hook. One sentence, concrete, not generic.
5. Reference ONE other signal only if it naturally reinforces the hook. Do not force it.
6. NEVER list signals. NEVER write "we also noticed..." or "we saw that...".
7. The email must read like a thoughtful human wrote it — not a system report.
8. The body field must follow this exact format:
   Hi [first name],

   [2–4 lines of email content]

   [CTA sentence]

   Best regards,
   [Sender Name]
9. Do NOT include the greeting or sign-off in the line count — the 5–7 line limit applies to the content only.
10. Record which signal was the main hook and which (if any) was supporting.

## Output Format
Return valid JSON only. No markdown, no extra text.
{{
  "subject": "...",
  "body": "...",
  "hook_title": "...",
  "hook_summary": "...",
  "tone_used": "{tone.split('(')[1].split(')')[0] if '(' in tone else tone.split('.')[0].replace('PERSONALITY: ', '')}",
  "main_signal_used": "one-line description of the primary signal used",
  "supporting_signal_used": "one-line description or empty string if none used",
  "cta_type": "one of: direct_question | evidence_question | collaborative_offer | forward_question | open_question"
}}
"""

    def _parse(self, text: str) -> dict:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "subject" in data:
                return self._fill_defaults(data)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                    if isinstance(data, dict):
                        return self._fill_defaults(data)
                except json.JSONDecodeError:
                    pass
        return {
            "subject": "", "body": text,
            "hook_title": "", "hook_summary": "",
            "tone_used": "", "main_signal_used": "",
            "supporting_signal_used": "", "cta_type": "",
            "error": "Could not parse JSON response",
        }

    def _fill_defaults(self, data: dict) -> dict:
        defaults = {
            "subject": "", "body": "",
            "hook_title": "", "hook_summary": "",
            "tone_used": "", "main_signal_used": "",
            "supporting_signal_used": "", "cta_type": "",
        }
        for k, v in defaults.items():
            data.setdefault(k, v)
        return data

    def _check_length(self, result: dict) -> dict:
        body = result.get("body", "")
        lines = [l for l in body.splitlines() if l.strip()]
        if len(lines) > MAX_BODY_LINES:
            result["length_warning"] = (
                f"Email is {len(lines)} lines — consider trimming to {MAX_BODY_LINES} or fewer."
            )
        return result
