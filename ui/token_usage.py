from __future__ import annotations
import streamlit as st
from ui.results_store import list_runs, load_run
from ui.theme import inject_theme
from agents.director import ROLE_TERRITORY_MANAGER, ROLE_VELOCITY

inject_theme()

# Claude Sonnet 4.6 pricing (USD per million tokens)
_PRICE_INPUT_PER_M = 3.00
_PRICE_OUTPUT_PER_M = 15.00

_AGENT_LABELS = {
    "tech_stack":                "Tech Stack",
    "hiring_patterns":           "Hiring Signals",
    "public_news":               "Public News",
    "company_position":          "Company Position",
    "regulatory_impact":         "Regulatory Impact",
    "company_profile":           "Company Profile",
    "stakeholder_intelligence":  "Stakeholder Intelligence",
    "pain_points":               "Developer Pain Points",
}

_ENT_AGENTS = [
    "tech_stack", "hiring_patterns", "public_news",
    "company_position", "regulatory_impact",
    "company_profile", "stakeholder_intelligence",
]

_VEL_AGENTS = [
    "tech_stack", "hiring_patterns", "public_news",
    "company_position", "company_profile", "pain_points",
]

_SCALE_ENT = [1, 10, 50, 100, 200, 300, 500]
_SCALE_VEL = [1, 5, 10, 25, 50, 100]


def _cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1_000_000 * _PRICE_INPUT_PER_M
            + output_tokens / 1_000_000 * _PRICE_OUTPUT_PER_M)


def _load_averages(role: str, agent_keys: list[str]) -> dict | None:
    """Return per-agent average token usage across all saved runs for a role.
    Returns None if no token_usage data found."""
    runs = list_runs(role)
    if not runs:
        return None

    sums: dict[str, dict] = {k: {"input": 0, "output": 0} for k in agent_keys}
    counts: dict[str, int] = {k: 0 for k in agent_keys}

    for run_meta in runs:
        try:
            run = load_run(run_meta["path"])
        except Exception:
            continue
        for result in run.get("results", []):
            usage = result.get("token_usage", {})
            if not usage:
                continue
            for key in agent_keys:
                if key in usage:
                    sums[key]["input"] += usage[key].get("input", 0)
                    sums[key]["output"] += usage[key].get("output", 0)
                    counts[key] += 1

    # Need at least one data point to return averages
    if not any(counts[k] > 0 for k in agent_keys):
        return None

    avgs: dict[str, dict] = {}
    for key in agent_keys:
        n = counts[key]
        if n > 0:
            avgs[key] = {
                "input":  round(sums[key]["input"] / n),
                "output": round(sums[key]["output"] / n),
                "samples": n,
            }
    return avgs if avgs else None


def _render_section(title: str, role: str, agent_keys: list[str], scale_rows: list[int]):
    st.subheader(title)

    avgs = _load_averages(role, agent_keys)

    if avgs:
        # ── Per-agent breakdown ───────────────────────────────────────────────
        st.markdown("#### Per-Agent Breakdown (averaged from actual runs)")

        total_in = sum(v["input"] for v in avgs.values())
        total_out = sum(v["output"] for v in avgs.values())

        rows_html = ""
        for key in agent_keys:
            if key not in avgs:
                continue
            d = avgs[key]
            total_tok = d["input"] + d["output"]
            pct = round(total_tok / (total_in + total_out) * 100) if (total_in + total_out) > 0 else 0
            c = _cost(d["input"], d["output"])
            rows_html += (
                f"<tr>"
                f"<td style='color:#f8fafc'>{_AGENT_LABELS.get(key, key)}</td>"
                f"<td style='color:#94a3b8;text-align:right'>{d['input']:,}</td>"
                f"<td style='color:#94a3b8;text-align:right'>{d['output']:,}</td>"
                f"<td style='color:#f8fafc;font-weight:600;text-align:right'>{total_tok:,}</td>"
                f"<td style='color:#00d4aa;text-align:right'>${c:.4f}</td>"
                f"<td style='color:#94a3b8;text-align:right'>{pct}%</td>"
                f"<td style='color:#64748b;font-size:0.75rem;text-align:right'>{d['samples']} co.</td>"
                f"</tr>"
            )

        total_cost = _cost(total_in, total_out)
        rows_html += (
            f"<tr style='border-top:2px solid #1e293b'>"
            f"<td style='color:#f8fafc;font-weight:700'>TOTAL per company</td>"
            f"<td style='color:#f8fafc;font-weight:700;text-align:right'>{total_in:,}</td>"
            f"<td style='color:#f8fafc;font-weight:700;text-align:right'>{total_out:,}</td>"
            f"<td style='color:#00d4aa;font-weight:700;text-align:right'>{total_in+total_out:,}</td>"
            f"<td style='color:#00d4aa;font-weight:700;text-align:right'>${total_cost:.4f}</td>"
            f"<td></td><td></td>"
            f"</tr>"
        )

        st.markdown(f"""
<table style='width:100%;border-collapse:separate;border-spacing:0 4px;font-size:0.85rem'>
  <thead>
    <tr>
      <th style='color:#94a3b8;text-align:left;padding:6px 0;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em'>Agent</th>
      <th style='color:#94a3b8;text-align:right;padding:6px 8px;font-size:0.7rem;text-transform:uppercase'>Input</th>
      <th style='color:#94a3b8;text-align:right;padding:6px 8px;font-size:0.7rem;text-transform:uppercase'>Output</th>
      <th style='color:#94a3b8;text-align:right;padding:6px 8px;font-size:0.7rem;text-transform:uppercase'>Total</th>
      <th style='color:#94a3b8;text-align:right;padding:6px 8px;font-size:0.7rem;text-transform:uppercase'>Cost</th>
      <th style='color:#94a3b8;text-align:right;padding:6px 8px;font-size:0.7rem;text-transform:uppercase'>Share</th>
      <th style='color:#94a3b8;text-align:right;padding:6px 8px;font-size:0.7rem;text-transform:uppercase'>Data</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>""", unsafe_allow_html=True)

    else:
        st.info(
            "No token data yet — run a research batch first. "
            "Once you've researched at least one company, this page will show "
            "real token counts and cost projections based on your actual usage."
        )
        return

    st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)

    # ── Scale projections ─────────────────────────────────────────────────────
    st.markdown("#### Scale Projections")
    if not avgs:
        return

    total_in  = sum(v["input"]  for v in avgs.values())
    total_out = sum(v["output"] for v in avgs.values())

    proj_rows = ""
    for n in scale_rows:
        proj_in  = total_in  * n
        proj_out = total_out * n
        proj_tok = proj_in + proj_out
        proj_cost = _cost(proj_in, proj_out)
        proj_rows += (
            f"<tr>"
            f"<td style='color:#f8fafc;font-weight:600;text-align:center'>{n}</td>"
            f"<td style='color:#94a3b8;text-align:right'>{proj_in:,}</td>"
            f"<td style='color:#94a3b8;text-align:right'>{proj_out:,}</td>"
            f"<td style='color:#f8fafc;font-weight:600;text-align:right'>{proj_tok:,}</td>"
            f"<td style='color:#00d4aa;font-weight:700;text-align:right'>${proj_cost:.2f}</td>"
            f"</tr>"
        )

    st.markdown(f"""
<table style='width:100%;border-collapse:separate;border-spacing:0 4px;font-size:0.85rem'>
  <thead>
    <tr>
      <th style='color:#94a3b8;text-align:center;padding:6px 0;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em'>Companies</th>
      <th style='color:#94a3b8;text-align:right;padding:6px 8px;font-size:0.7rem;text-transform:uppercase'>Input Tokens</th>
      <th style='color:#94a3b8;text-align:right;padding:6px 8px;font-size:0.7rem;text-transform:uppercase'>Output Tokens</th>
      <th style='color:#94a3b8;text-align:right;padding:6px 8px;font-size:0.7rem;text-transform:uppercase'>Total Tokens</th>
      <th style='color:#94a3b8;text-align:right;padding:6px 8px;font-size:0.7rem;text-transform:uppercase'>Est. Cost (USD)</th>
    </tr>
  </thead>
  <tbody>
    {proj_rows}
  </tbody>
</table>""", unsafe_allow_html=True)

    st.caption(
        f"Pricing: ${_PRICE_INPUT_PER_M}/M input · ${_PRICE_OUTPUT_PER_M}/M output "
        f"(Claude Sonnet 4.6 standard). Based on actual data from your runs."
    )


# ── Page ──────────────────────────────────────────────────────────────────────

st.title("Token Usage")
st.markdown("Track how many tokens each research run consumes and project costs at scale.")
st.markdown("---")

ent_tab, vel_tab = st.tabs(["🏢 ENT (Territory Manager)", "⚡ Velocity (Mid-market)"])

with ent_tab:
    _render_section(
        "Enterprise Research — Token Usage",
        ROLE_TERRITORY_MANAGER,
        _ENT_AGENTS,
        _SCALE_ENT,
    )

with vel_tab:
    _render_section(
        "Velocity Research — Token Usage",
        ROLE_VELOCITY,
        _VEL_AGENTS,
        _SCALE_VEL,
    )
