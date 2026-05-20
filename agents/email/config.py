PERSONALITY_TONES = {
    "Red": (
        "PERSONALITY: Red (Driver). Results-driven, decisive, direct. No fluff. "
        "Lead with ROI, risk reduction, or efficiency gain. Short sentences. "
        "They want to know the outcome and why it matters now — not the story behind it. "
        "CTA: ask a direct, binary question — e.g. 'Worth a 15-min call this week?'"
    ),
    "Blue": (
        "PERSONALITY: Blue (Analytical). Detail-oriented, evidence-driven, skeptical of unsupported claims. "
        "Lead with a specific, verifiable fact. Reference data or a concrete finding. "
        "Do not make claims that cannot be supported. They will fact-check anything vague. "
        "CTA: ask an evidence-based question — e.g. 'Would it be useful to walk through how other "
        "[industry] teams have handled this?'"
    ),
    "Green": (
        "PERSONALITY: Green (Amiable). Values relationships, team harmony, and collaboration. "
        "Lead with shared context or a team-level impact. Frame Sonar as a partner, not a vendor. "
        "Avoid aggressive language. Warm but professional. "
        "CTA: offer to collaborate — e.g. 'Happy to share how similar teams approached this, if that would be helpful.'"
    ),
    "Yellow": (
        "PERSONALITY: Yellow (Expressive). Enthusiastic, visionary, drawn to innovation and big ideas. "
        "Lead with a forward-looking angle — where the industry is heading, not just where it is now. "
        "Connect Sonar to their innovation or transformation story. "
        "CTA: paint a forward-looking question — e.g. 'Curious how you're thinking about code quality as you scale that initiative?'"
    ),
    "Unknown": (
        "PERSONALITY: Unknown. Use a neutral, professional tone. "
        "Lead with the most specific, concrete signal from the evidence. "
        "Be direct without being aggressive. Let the facts do the work. "
        "CTA: ask an open question — e.g. 'Would it make sense to compare notes on this?'"
    ),
}

def build_tone_guidance(personalities: list[str]) -> str:
    """Return tone instruction string for one or more personality colours."""
    valid = [p for p in personalities if p in PERSONALITY_TONES]
    if not valid:
        return PERSONALITY_TONES["Unknown"]
    if len(valid) == 1:
        return PERSONALITY_TONES[valid[0]]
    labels = " / ".join(valid)
    individual_notes = "\n".join(
        f"  - {p}: {PERSONALITY_TONES[p].split('. ', 1)[1] if '. ' in PERSONALITY_TONES[p] else PERSONALITY_TONES[p]}"
        for p in valid
    )
    return (
        f"PERSONALITY: {labels} (blended). This person shows traits of multiple styles — adapt accordingly.\n"
        f"{individual_notes}\n"
        f"Blend these styles: be specific and evidence-grounded, but also decisive and outcome-focused. "
        f"Do not write a generic email — let the dominant signal in the evidence choose which style leads."
    )


HOOK_QUALITY_RULES = """\
HOOK QUALITY RULES — the hook_title must be:
- Specific to this company's situation, not generic
- Role-relevant: framed for what this person cares about
- Time-relevant: references something happening now (acquisition, regulation, hiring surge, etc.)
- Problem-led: surfaces the tension or risk, not the solution

FORBIDDEN hook titles (too generic):
- "Improving code quality"
- "Enhancing software security"
- "Supporting developers"
- "Helping with DevOps"
- "Better code practices"

STRONG hook title examples:
- "Scaling AI delivery without letting code risk pile up"
- "Cutting quality-gate friction as DevSecOps hiring ramps"
- "Staying audit-ready as engineering expands post-acquisition"
- "Reducing scan noise while AppSec matures"
- "Keeping cloud transformation from creating hidden code debt"
"""

SYSTEM_PROMPT = """\
You are an expert B2B sales email writer for Sonar (formerly SonarSource).

Sonar makes code quality and security tools: SonarQube (self-hosted), SonarCloud (SaaS), \
and SonarLint (IDE plugin). They help development teams catch bugs, vulnerabilities, and \
code smells before code reaches production. Key value props: shift-left security, developer \
productivity, compliance-ready code quality gates.

Your job: write ONE short, human outreach email. Not a pitch deck. Not a summary report. \
The only goal is to earn a single reply from the target person.
"""

MAX_BODY_LINES = 8
