"""
Shared rendering helpers for account list and account detail tabs.
Used by ent_accounts.py and velocity_accounts.py.

Layered on top of ui.design (tokens) and ui.components (primitives).
Public API: render_run_content, render_account_content, add_tab, prefetch_advisor.
"""
from __future__ import annotations

import io
import json
import re
import streamlit as st
import streamlit.components.v1 as components
from collections import Counter

from agents.director import (
    AGENT_TECH_STACK, AGENT_HIRING, AGENT_NEWS,
    AGENT_POSITION, AGENT_REGULATORY, AGENT_PROFILE, AGENT_STAKEHOLDER, AGENT_PAIN_POINTS,
    AGENT_ADVISOR,
)
from config.settings import MIN_NEWS_COUNT

from ui.design import (
    ACCENT, ACCENT_80, ACCENT_SOFT, BORDER, BORDER_HI, CARD, CARD_HOVER,
    DANGER, INFO, MUTED, PERSONALITY_COLORS, POSITION_COLORS, RADIUS, SIGNAL_COLORS,
    SPACE, TEXT, TEXT_DIM, TYPE, WARN,
)
from ui.components import (
    bullets_html, card_close, card_open, divider, kv_row, metric_card, micro_label,
    pill, pill_html, score_bar, score_bar_html, section_header, spacer,
)

# ── Lookup tables (preserved from original) ────────────────────────────────

_CATEGORY_LABELS = {
    "devsecops_appsec":            "DevSecOps / AppSec",
    "devops_platform":             "DevOps / Platform",
    "software_engineering_growth": "Software Engineering",
    "cloud_infrastructure":        "Cloud / Infrastructure",
    "security_compliance":         "Security / Compliance",
    "devsecops":                   "DevSecOps / AppSec",
    "devops":                      "DevOps / Platform",
    "software_engineer":           "Software Engineering",
    "security":                    "Security",
    "cloud":                       "Cloud / Infrastructure",
    "language":                    "Language Signal",
}

_WHY_NEWS = {
    "cybersecurity_incident":   "Active security incident — urgent pressure to improve code security posture",
    "cloud_ai_transformation":  "Cloud/AI transformation means new code being written — quality gate needs grow",
    "product_platform_launch":  "New product or platform launch signals active development — potential quality gaps",
    "engineering_investment":   "Engineering investment signals growing dev teams — code quality standards need to scale",
    "leadership_change":        "Leadership change often triggers technology stack reviews",
    "security_incident":        "Active security incident — urgent pressure to improve code security posture",
    "compliance_regulatory":    "Regulatory requirement — compliance deadlines drive SAST/code quality investment",
    "cloud_ai_initiative":      "Cloud/AI expansion means more code being written — quality gate needs grow",
    "product_launch":           "New product launch signals active development — potential quality gaps",
    "acquisition":              "M&A activity creates code integration challenges across teams",
    "hiring_wave":              "Hiring surge indicates growing dev teams — code quality standards need to scale",
}

_REG_RELEVANCE = {
    "active_fine_lawsuit":          "Active enforcement — urgent compliance need",
    "specific_regulation_applies":  "Direct regulation — Sonar addresses requirement",
    "compliance_audit":             "Audit activity — code quality under scrutiny",
    "regulated_industry":           "Regulated industry — compliance baseline expected",
    "regional_regulator_relevance": "Regional regulator active in this space",
    "general_regulatory_mention":   "General regulatory context",
}

_PAIN_CATEGORY_LABELS = {
    "security_incident_pain":   "Security Incident",
    "code_quality_pain":        "Code Quality",
    "static_analysis_pain":     "Static Analysis",
    "ci_cd_integration_pain":   "CI/CD Integration",
    "technical_debt_pain":      "Technical Debt",
    "developer_velocity_pain":  "Developer Velocity",
    "competitor_tooling_pain":  "Competitor Tooling",
    "sonar_specific_pain":      "Sonar-Specific",
}

_PAIN_CATEGORY_COLORS = {
    "security_incident_pain":   DANGER,
    "code_quality_pain":        WARN,
    "static_analysis_pain":     INFO,
    "ci_cd_integration_pain":   "#8b5cf6",
    "technical_debt_pain":      "#f97316",
    "developer_velocity_pain":  "#06b6d4",
    "competitor_tooling_pain":  "#ec4899",
    "sonar_specific_pain":      ACCENT,
}

_PERSONALITY_OPTIONS  = ["Red", "Blue", "Green", "Yellow", "Unknown"]
_PERSONALITY_DESCS = {
    "Red":     "Direct, results-focused, no fluff",
    "Blue":    "Analytical, evidence-based, detailed",
    "Green":   "Relationship-driven, collaborative, warm",
    "Yellow":  "Visionary, enthusiastic, big-picture",
    "Unknown": "Neutral, professional, fact-led",
}

# Tone presets — appended to strategy_note so we don't change the agent contract
_TONE_PRESETS = {
    "Direct":        "Style hint: keep the email under 7 lines. Lead with the outcome / value. No filler.",
    "Warmer":        "Style hint: open with a warmer, more conversational hook. Acknowledge the contact's context before pitching.",
    "Shorter":       "Style hint: cut to under 60 words total. One tight paragraph, one CTA.",
    "More technical":"Style hint: lean into technical specifics in the body — name the languages/tools/frameworks where evidence supports it. Speak as engineer-to-engineer.",
}


# ── Internal helpers ────────────────────────────────────────────────────────

def _ck(company: str) -> str:
    """Safe session-state key prefix from company name."""
    return re.sub(r"\W+", "_", company.lower()).strip("_")


def _html_table(rows: list[dict], link_cols: set | None = None, col_styles: dict | None = None) -> str:
    if not rows:
        return ""
    headers = list(rows[0].keys())
    link_cols = link_cols or set()
    col_styles = col_styles or {}
    ths = "".join(f"<th style='{col_styles.get(h, '')}'>{h}</th>" for h in headers)
    body = ""
    for row in rows:
        tds = ""
        for h in headers:
            val = row.get(h, "") or ""
            style = col_styles.get(h, "")
            if h in link_cols and val:
                tds += f"<td style='{style}'><a class='si-link' href='{val}' target='_blank'>VIEW ↗</a></td>"
            else:
                tds += f"<td style='{style}'>{val}</td>"
        body += f"<tr>{tds}</tr>"
    return f"<table class='si-table'><thead><tr>{ths}</tr></thead><tbody>{body}</tbody></table>"


def _industry(r: dict) -> str:
    return (
        r.get("industry") or r.get("Industry")
        or r["signals"].get(AGENT_REGULATORY, {}).get("industry_detected", "—")
        or "—"
    ).capitalize()


def _position_label(r: dict) -> str:
    return r["signals"].get(AGENT_POSITION, {}).get("position_label", "—")


def _score_breakdown(r: dict) -> dict[str, float]:
    """Per-signal score contribution dict — used by score_bar."""
    sigs = r.get("signals", {})
    out = {}
    for key, label in [
        (AGENT_TECH_STACK,   "tech_stack"),
        (AGENT_HIRING,       "hiring"),
        (AGENT_NEWS,         "news"),
        (AGENT_POSITION,     "company_position"),
        (AGENT_REGULATORY,   "regulatory"),
        (AGENT_PAIN_POINTS,  "pain_points"),
    ]:
        s = sigs.get(key, {}) or {}
        score = s.get("sonar_relevance_score", 0) or 0
        if score:
            out[label] = float(score)
    return out


def _top_signal(r: dict) -> tuple[str, float]:
    bk = _score_breakdown(r)
    if not bk:
        return ("—", 0.0)
    k, v = max(bk.items(), key=lambda kv: kv[1])
    return (k.replace("_", " ").title(), v)


def prefetch_advisor(r: dict):
    """Load stored Signal Advisor result into session state — no API call."""
    ck = _ck(r["company"])
    if f"adv_result_{ck}" in st.session_state:
        return
    stored = r.get("signals", {}).get(AGENT_ADVISOR)
    st.session_state[f"adv_result_{ck}"] = stored if stored else {}


def add_tab(tabs_key: str, tab_config: dict):
    for i, existing in enumerate(st.session_state[tabs_key]):
        if existing.get("type") == tab_config.get("type") and existing.get("label") == tab_config.get("label"):
            st.session_state[tabs_key + "_navigate_to"] = i + 1
            return
    st.session_state[tabs_key].append(tab_config)
    st.session_state[tabs_key + "_navigate_to"] = len(st.session_state[tabs_key])


# ── Ranked-table dashboard ─────────────────────────────────────────────────

_SORT_FIELDS = {
    "rank":     lambda r: r.get("rank", 0),
    "company":  lambda r: (r.get("company") or "").lower(),
    "industry": lambda r: _industry(r).lower(),
    "score":    lambda r: -float(r.get("total_score", 0)),  # desc by default
    "position": lambda r: _position_label(r),
}


def _apply_sort_and_filter(results: list, tabs_key: str, run_path: str) -> list:
    sort_key = st.session_state.get(f"{tabs_key}_{run_path}_sort", "rank")
    sort_dir = st.session_state.get(f"{tabs_key}_{run_path}_sortdir", "asc")
    query    = st.session_state.get(f"{tabs_key}_{run_path}_search", "").strip().lower()

    items = list(results)
    if query:
        items = [r for r in items if query in (r.get("company") or "").lower()
                 or query in _industry(r).lower()]

    keyfn = _SORT_FIELDS.get(sort_key, _SORT_FIELDS["rank"])
    items.sort(key=keyfn)
    if sort_dir == "desc":
        items.reverse()
    return items


def _toggle_sort(tabs_key: str, run_path: str, field: str):
    cur = st.session_state.get(f"{tabs_key}_{run_path}_sort", "rank")
    cur_dir = st.session_state.get(f"{tabs_key}_{run_path}_sortdir", "asc")
    if cur == field:
        st.session_state[f"{tabs_key}_{run_path}_sortdir"] = "desc" if cur_dir == "asc" else "asc"
    else:
        st.session_state[f"{tabs_key}_{run_path}_sort"] = field
        st.session_state[f"{tabs_key}_{run_path}_sortdir"] = "asc" if field != "score" else "desc"


def _sort_arrow(tabs_key: str, run_path: str, field: str) -> str:
    cur = st.session_state.get(f"{tabs_key}_{run_path}_sort", "rank")
    if cur != field:
        return ""
    d = st.session_state.get(f"{tabs_key}_{run_path}_sortdir", "asc")
    return " ↓" if d == "desc" else " ↑"


def render_run_content(results: list, run_path: str, tabs_key: str, show_position: bool = True):
    """Dashboard ranked-table view for a single run."""
    search_key = f"{tabs_key}_{run_path}_search"
    sel_prefix = f"{tabs_key}_{run_path}_sel_"

    # ── Toolbar: search + bulk actions ────────────────────────────────────
    tb_search, tb_actions = st.columns([2.5, 2])
    with tb_search:
        st.text_input(
            "Search company / industry",
            key=search_key,
            placeholder="Filter by name or industry…",
            label_visibility="collapsed",
        )

    selected_idxs = [
        int(k[len(sel_prefix):]) for k in st.session_state
        if k.startswith(sel_prefix) and st.session_state[k]
    ]
    n_sel = len(selected_idxs)

    with tb_actions:
        a1, a2, a3 = st.columns(3)
        with a1:
            csv_bytes = _build_csv(results)
            st.download_button(
                f"⤓ CSV (all)",
                data=csv_bytes,
                file_name=f"{_safe_filename(run_path)}.csv",
                mime="text/csv",
                key=f"{tabs_key}_{run_path}_csv_all",
                use_container_width=True,
            )
        with a2:
            sel_csv = _build_csv([results[i] for i in selected_idxs]) if selected_idxs else b""
            st.download_button(
                f"⤓ CSV ({n_sel})",
                data=sel_csv,
                file_name=f"{_safe_filename(run_path)}_selected.csv",
                mime="text/csv",
                key=f"{tabs_key}_{run_path}_csv_sel",
                disabled=n_sel == 0,
                use_container_width=True,
            )
        with a3:
            md_bytes = _build_markdown(results, selected_idxs) if selected_idxs else b""
            st.download_button(
                f"⤓ Brief ({n_sel})",
                data=md_bytes,
                file_name=f"{_safe_filename(run_path)}_brief.md",
                mime="text/markdown",
                key=f"{tabs_key}_{run_path}_md_sel",
                disabled=n_sel == 0,
                use_container_width=True,
            )

    spacer("sm")

    # ── Header row (clickable for sort) ───────────────────────────────────
    cols_spec = [0.4, 0.5, 2.8, 2.2, 2.6, 1.8] if show_position else [0.4, 0.5, 2.8, 2.2, 2.6]
    header_cols = st.columns(cols_spec)

    header_cols[0].markdown(
        f"<div style='color:{MUTED};font-size:{TYPE['micro']};text-transform:uppercase;"
        f"letter-spacing:0.08em;padding-top:8px'>✓</div>",
        unsafe_allow_html=True,
    )
    sort_labels = [("rank", "RANK"), ("company", "COMPANY"), ("industry", "INDUSTRY"),
                   ("score", "SCORE")]
    if show_position:
        sort_labels.append(("position", "POSITION"))

    for col, (field, label) in zip(header_cols[1:], sort_labels):
        with col:
            if st.button(
                f"{label}{_sort_arrow(tabs_key, run_path, field)}",
                key=f"{tabs_key}_{run_path}_sort_{field}",
                type="tertiary",
                use_container_width=True,
            ):
                _toggle_sort(tabs_key, run_path, field)
                st.rerun()

    st.markdown(
        f"<hr style='border:0;border-top:1px solid {BORDER};margin:4px 0 6px 0'>",
        unsafe_allow_html=True,
    )

    visible = _apply_sort_and_filter(results, tabs_key, run_path)
    if not visible:
        st.caption("No accounts match your filter.")
        return

    # ── Body rows ─────────────────────────────────────────────────────────
    for r in visible:
        # Find original index (selection state uses original indices)
        orig_idx = results.index(r)
        industry = _industry(r)
        score = round(r["total_score"], 1)
        breakdown = _score_breakdown(r)

        row_cols = st.columns(cols_spec)
        with row_cols[0]:
            st.checkbox(
                "Select",
                key=f"{sel_prefix}{orig_idx}",
                label_visibility="collapsed",
            )

        row_cols[1].markdown(
            f"<div style='color:{MUTED};font-weight:600;padding-top:10px'>{r['rank']}</div>",
            unsafe_allow_html=True,
        )

        with row_cols[2]:
            if st.button(
                r["company"],
                key=f"row_{tabs_key}_{orig_idx}",
                type="tertiary",
            ):
                add_tab(tabs_key, {
                    "type": "account", "run_path": run_path,
                    "idx": orig_idx, "label": r["company"],
                })
                st.rerun()

        row_cols[3].markdown(
            f"<div style='color:{TEXT_DIM};padding-top:10px;font-size:{TYPE['small']}'>{industry}</div>",
            unsafe_allow_html=True,
        )

        row_cols[4].markdown(
            f"<div style='padding-top:8px'>{score_bar_html(breakdown, total=score, width_px=180)}</div>",
            unsafe_allow_html=True,
        )

        if show_position:
            position = _position_label(r)
            pos_color = POSITION_COLORS.get(position, MUTED)
            row_cols[5].markdown(
                f"<div style='padding-top:8px'>{pill_html(position, pos_color)}</div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            f"<hr style='border:0;border-top:1px solid {BORDER};margin:2px 0'>",
            unsafe_allow_html=True,
        )


def _safe_filename(run_path: str) -> str:
    import os
    base = os.path.basename(run_path)
    return re.sub(r"\.json$", "", base)


def _build_csv(results: list) -> bytes:
    import csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "rank", "company", "domain", "industry", "score", "position",
        "tech_score", "hiring_score", "news_score", "regulatory_score",
        "pain_score", "top_signal",
    ])
    for r in results:
        bk = _score_breakdown(r)
        top, _ = _top_signal(r)
        w.writerow([
            r.get("rank", ""),
            r.get("company", ""),
            r.get("domain", ""),
            _industry(r),
            round(r.get("total_score", 0), 2),
            _position_label(r),
            round(bk.get("tech_stack", 0), 2),
            round(bk.get("hiring", 0), 2),
            round(bk.get("news", 0), 2),
            round(bk.get("regulatory", 0), 2),
            round(bk.get("pain_points", 0), 2),
            top,
        ])
    return buf.getvalue().encode("utf-8")


def _build_markdown(results: list, idxs: list[int]) -> bytes:
    """Compact briefing markdown of N selected accounts — Slack/email friendly."""
    lines: list[str] = []
    for i in idxs:
        r = results[i]
        sigs = r.get("signals", {})
        lines.append(f"# {r['company']}  (Rank #{r['rank']} · Score {round(r['total_score'], 1)})")
        lines.append(f"*Industry:* {_industry(r)}  ·  *Position:* {_position_label(r)}  ·  *Domain:* {r.get('domain', '—')}")
        adv = sigs.get(AGENT_ADVISOR, {}) or {}
        if adv.get("hook_title"):
            lines.append(f"\n**Recommended hook:** {adv['hook_title']}")
        if adv.get("hook_rationale"):
            lines.append(adv["hook_rationale"])
        for key, label in [
            (AGENT_TECH_STACK,  "Tech Stack"),
            (AGENT_HIRING,      "Hiring"),
            (AGENT_NEWS,        "Public News"),
            (AGENT_REGULATORY,  "Regulatory"),
            (AGENT_PAIN_POINTS, "Pain Points"),
        ]:
            s = sigs.get(key) or {}
            score = s.get("sonar_relevance_score")
            summary = s.get("summary", "")
            if score is None and not summary:
                continue
            lines.append(f"\n## {label}  (score {score}/10)")
            if summary:
                lines.append(summary)
        lines.append("\n---\n")
    return "\n".join(lines).encode("utf-8")


# ── Account detail ─────────────────────────────────────────────────────────

def render_account_content(r: dict, show_email: bool = False, velocity_mode: bool = False, run_path: str = ""):
    sigs = r["signals"]
    ck = _ck(r["company"])

    # ── Hero header ─────────────────────────────────────────────────────────
    _render_hero(r, sigs, velocity_mode=velocity_mode)
    spacer("md")

    # ── Main body: content + sticky reasons rail ────────────────────────────
    body_col, rail_col = st.columns([2.6, 1], gap="large")

    # The selected-items list is filled by signal-tab checkboxes (when
    # show_email=True) and consumed by the Email tab. We attach to session
    # state keyed by company so it survives tab clicks.
    sel_key = f"selected_items_{ck}"
    st.session_state[sel_key] = []

    with body_col:
        tab_specs = _resolve_tabs(sigs, velocity_mode=velocity_mode, show_email=show_email)
        labels = [t[0] for t in tab_specs]
        tabs = st.tabs(labels)
        for tab_widget, (_, render_fn) in zip(tabs, tab_specs):
            with tab_widget:
                render_fn(r, sigs, ck, show_email, velocity_mode, run_path)

    with rail_col:
        _render_reasons_rail(r, sigs, ck, run_path)


def _resolve_tabs(sigs: dict, velocity_mode: bool, show_email: bool) -> list[tuple[str, callable]]:
    specs: list[tuple[str, callable]] = [("Overview", _tab_overview)]
    if sigs.get(AGENT_TECH_STACK):
        specs.append(("Tech", _tab_tech))
    if sigs.get(AGENT_HIRING):
        specs.append(("Hiring", _tab_hiring))
    if sigs.get(AGENT_NEWS):
        specs.append(("News", _tab_news))
    if velocity_mode:
        if sigs.get(AGENT_PAIN_POINTS):
            specs.append(("Pain Points", _tab_pain))
    else:
        if sigs.get(AGENT_STAKEHOLDER) or sigs.get(AGENT_REGULATORY):
            specs.append(("People & Regs", _tab_people_regs))
    if show_email:
        specs.append(("✉ Email", _tab_email))
    return specs


# ── Hero & sticky rail ─────────────────────────────────────────────────────

def _render_hero(r: dict, sigs: dict, velocity_mode: bool = False):
    score = round(r["total_score"], 1)
    top_name, top_score = _top_signal(r)
    position = _position_label(r)
    pos_color = POSITION_COLORS.get(position, MUTED)
    industry = _industry(r)

    # Company strip
    domain = r.get("domain", "")
    domain_link = (
        f"<a href='https://{domain}' target='_blank' style='color:{ACCENT};"
        f"text-decoration:none;font-size:{TYPE['caption']}'>{domain} ↗</a>"
        if domain else ""
    )
    st.markdown(
        f"<div style='display:flex;align-items:baseline;gap:14px;flex-wrap:wrap'>"
        f"<span style='color:{MUTED};font-size:{TYPE['caption']}'>Rank #{r['rank']}</span>"
        f"{domain_link}"
        f"</div>",
        unsafe_allow_html=True,
    )

    spacer("sm")

    cols = st.columns(4, gap="medium")
    with cols[0]:
        metric_card("Propensity Score", f"{score}", sublabel="out of available signals")
    with cols[1]:
        metric_card("Top Signal", top_name,
                    sublabel=f"contributing {top_score:.1f}/10",
                    accent=SIGNAL_COLORS.get(top_name.lower().replace(" ", "_"), ACCENT))
    with cols[2]:
        if not velocity_mode:
            metric_card("Position", position, accent=pos_color, size="md")
        else:
            n_pain = len((sigs.get(AGENT_PAIN_POINTS, {}) or {}).get("evidence", []))
            metric_card("Pain Signals", str(n_pain), sublabel="evidence items", size="md")
    with cols[3]:
        metric_card("Industry", industry, size="md", accent=MUTED)

    spacer("sm")
    bk = _score_breakdown(r)
    if bk:
        micro_label("Signal Breakdown")
        score_bar(bk, total=score)


def _render_reasons_rail(r: dict, sigs: dict, ck: str, run_path: str):
    """Sticky right rail — Recommended Hook + reasons to engage."""
    adv = st.session_state.get(f"adv_result_{ck}") or sigs.get(AGENT_ADVISOR) or {}
    st.markdown(
        f"<div class='si-sticky-rail'>",
        unsafe_allow_html=True,
    )

    if adv.get("hook_title"):
        st.markdown(
            f"<div style='background:{ACCENT_SOFT};border:1px solid {ACCENT}55;"
            f"border-radius:{RADIUS['md']}px;padding:14px 16px;margin-bottom:12px'>"
            f"<div style='color:{ACCENT};font-size:{TYPE['micro']};font-weight:700;"
            f"text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px'>"
            f"Recommended Hook</div>"
            f"<div style='color:{TEXT};font-weight:700;font-size:{TYPE['small']};"
            f"line-height:1.4;margin-bottom:8px'>{adv['hook_title']}</div>"
            f"<div style='color:{TEXT_DIM};font-size:{TYPE['caption']};"
            f"line-height:1.55'>{adv.get('hook_rationale', '')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    suggested = adv.get("suggested_signals", [])
    if suggested:
        st.markdown(
            f"<div style='color:{MUTED};font-size:{TYPE['micro']};text-transform:uppercase;"
            f"letter-spacing:0.08em;font-weight:600;margin-bottom:6px'>"
            f"Reasons to Engage</div>",
            unsafe_allow_html=True,
        )
        items_html = "".join(
            f"<li style='color:{TEXT_DIM};font-size:{TYPE['caption']};line-height:1.55;"
            f"margin-bottom:6px'><strong style='color:{ACCENT}'>"
            f"{sig.get('type', '').replace('_', ' ').title()}</strong> — "
            f"{sig.get('label', '')}</li>"
            for sig in suggested
        )
        st.markdown(
            f"<ul style='margin:0;padding-left:18px'>{items_html}</ul>",
            unsafe_allow_html=True,
        )

    if not adv:
        st.markdown(
            f"<div style='background:rgba(148,163,184,0.06);border:1px solid {BORDER};"
            f"border-radius:{RADIUS['md']}px;padding:14px;color:{MUTED};"
            f"font-size:{TYPE['caption']}'>"
            f"Run the Outreach Suggest agent to surface a hook here.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ── Individual tabs ────────────────────────────────────────────────────────

def _tab_overview(r: dict, sigs: dict, ck: str, show_email: bool, velocity_mode: bool, run_path: str):
    profile = sigs.get(AGENT_PROFILE)
    snap = (profile or {}).get("snapshot") or {}

    if snap:
        section_header("Company Profile")
        for label, key in [
            ("What they do",     "what_they_do"),
            ("Who they sell to", "who_they_sell_to"),
            ("Business model",   "business_model"),
            ("Key acquisitions", "key_acquisition"),
            ("AI posture",       "ai_posture"),
        ]:
            val = snap.get(key, "")
            if val:
                kv_row(label, val)
        spacer("md")

    pos = sigs.get(AGENT_POSITION)
    if pos and pos.get("summary"):
        section_header("Position Summary",
                       subtitle=f"{pos.get('position_label','—')} · "
                                f"{pos.get('classification_score', 0)}/10")
        st.markdown(
            bullets_html(pos["summary"], color=TEXT_DIM, size="small"),
            unsafe_allow_html=True,
        )
        spacer("md")

    if not snap and not pos:
        st.caption("No overview data available.")


def _tab_tech(r: dict, sigs: dict, ck: str, show_email: bool, velocity_mode: bool, run_path: str):
    ts = sigs.get(AGENT_TECH_STACK) or {}
    section_header("Technology Stack",
                   subtitle=f"Score: {ts.get('sonar_relevance_score', 0)}/10")

    ev_lookup = {e["id"]: e for e in ts.get("evidence", [])}
    grouped_rows = []
    detail_rows = []
    for cat_label, items in [
        ("Language",       ts.get("languages", [])),
        ("CI/CD",          ts.get("cicd_tools", [])),
        ("Cloud / DevOps", ts.get("cloud", [])),
        ("Security Tool",  ts.get("security_tools", [])),
    ]:
        if not items:
            continue
        findings_str = "  ·  ".join(item.get("name", "") for item in items)
        first_url = next(
            (ev_lookup[ids[0]].get("source_url") or ev_lookup[ids[0]].get("repo_url", "")
             for item in items
             for ids in [item.get("evidence_ids", [])]
             if ids and ids[0] in ev_lookup
             and (ev_lookup[ids[0]].get("source_url") or ev_lookup[ids[0]].get("repo_url"))),
            "",
        )
        grouped_rows.append({
            "cat": cat_label, "findings": findings_str,
            "count": len(items), "url": first_url,
        })
        for item in items:
            ev_ids = item.get("evidence_ids", [])
            first_ev = ev_lookup.get(ev_ids[0]) if ev_ids else None
            detail_rows.append({
                "Category":   cat_label,
                "Finding":    item.get("name", "—"),
                "Evidence":   first_ev["evidence_text"] if first_ev else "—",
                "Source":     (first_ev.get("source_url") or first_ev.get("repo_url", "")) if first_ev else "",
                "Confidence": item.get("confidence", "—"),
            })

    if not grouped_rows:
        st.caption("No tech stack signals detected.")
        return

    sel_key = f"selected_items_{ck}"

    for idx, row in enumerate(grouped_rows):
        if show_email:
            cb, content = st.columns([0.06, 1])
            cb_state = cb.checkbox("Include in email", key=f"eml_{ck}_ts_{idx}", label_visibility="collapsed")
            if cb_state:
                st.session_state[sel_key].append({
                    "type": "tech_stack",
                    "content": f"{row['cat']}: {row['findings']}",
                })
            target = content
        else:
            target = st.container()

        link_html = (
            f"<a class='si-link' href='{row['url']}' target='_blank'>VIEW ↗</a>"
            if row["url"] else ""
        )
        target.markdown(
            f"<div class='si-row-card'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center'>"
            f"<div>"
            f"<span style='color:{TEXT};font-weight:600;font-size:{TYPE['small']};"
            f"margin-right:10px'>{row['cat']}</span>"
            f"{pill_html(str(row['count']) + ' findings', ACCENT)}"
            f"</div>{link_html}"
            f"</div>"
            f"<div style='color:{TEXT_DIM};margin-top:6px;font-size:{TYPE['small']};"
            f"line-height:1.5'>{row['findings']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    if detail_rows:
        with st.expander("View full evidence detail"):
            st.markdown(_html_table(detail_rows, link_cols={"Source"}),
                        unsafe_allow_html=True)


def _tab_hiring(r: dict, sigs: dict, ck: str, show_email: bool, velocity_mode: bool, run_path: str):
    hiring = sigs.get(AGENT_HIRING) or {}
    section_header("Hiring Signals",
                   subtitle=f"Score: {hiring.get('sonar_relevance_score', 0)}/10")
    if hiring.get("summary"):
        st.caption(hiring["summary"])

    all_evidence = [e for e in hiring.get("evidence", []) if e.get("counted_in_score")] or hiring.get("evidence", [])
    evidence = [e for e in all_evidence if e.get("source_url", "").strip()]
    hidden_count = len(all_evidence) - len(evidence)

    if not evidence:
        st.caption("No hiring signals detected.")
        return

    counts = Counter((e.get("value", ""), e.get("type", "")) for e in evidence)
    seen: set = set()
    deduped = []
    for e in evidence:
        key = (e.get("value", ""), e.get("type", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)

    sel_key = f"selected_items_{ck}"

    for idx, e in enumerate(deduped):
        cat = _CATEGORY_LABELS.get(e.get("type", ""), e.get("type", "—"))
        count_str = f"{counts[(e.get('value',''), e.get('type',''))]}+"
        url = e.get("source_url", "")
        link_html = f"<a class='si-link' href='{url}' target='_blank'>VIEW ↗</a>" if url else ""

        if show_email:
            cb, content = st.columns([0.06, 1])
            cb_state = cb.checkbox("Include in email", key=f"eml_{ck}_hire_{idx}", label_visibility="collapsed")
            if cb_state:
                st.session_state[sel_key].append({
                    "type": "hiring",
                    "content": f"Hiring for {e.get('value','—')} ({cat}) — {count_str} postings",
                })
            target = content
        else:
            target = st.container()

        target.markdown(f"""
<div class="si-row-card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span style="font-weight:600;color:{TEXT};font-size:{TYPE['small']}">{e.get('value','—')}</span>
    <span style="color:{ACCENT};font-size:{TYPE['caption']};font-weight:700">{count_str} postings</span>
  </div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px">
    <span style="color:{MUTED};font-size:{TYPE['caption']}">{cat}  ·  {e.get('confidence','—')}</span>
    {link_html}
  </div>
</div>""", unsafe_allow_html=True)

    if hidden_count > 0:
        st.caption(f"ℹ {hidden_count} signal(s) not shown — no source URL available to verify.")


def _tab_news(r: dict, sigs: dict, ck: str, show_email: bool, velocity_mode: bool, run_path: str):
    news = sigs.get(AGENT_NEWS) or {}
    section_header("Public News",
                   subtitle=f"Score: {news.get('sonar_relevance_score', 0)}/10")
    evidence = [e for e in news.get("evidence", []) if e.get("counted_in_score")]
    if not evidence:
        st.caption("No news evidence found.")
        return

    sel_key = f"selected_items_{ck}"
    for idx, e in enumerate(evidence):
        signal    = e.get("signal_type", "")
        date      = e.get("published_date", "") or ""
        headline  = e.get("title", "—")
        why       = _WHY_NEWS.get(signal, signal.replace("_", " ").title())
        url       = e.get("url", "")
        link_html = f"<a class='si-link' href='{url}' target='_blank'>READ ARTICLE ↗</a>" if url else ""

        if show_email:
            cb, content = st.columns([0.06, 1])
            cb_state = cb.checkbox("Include in email", key=f"eml_{ck}_news_{idx}", label_visibility="collapsed")
            if cb_state:
                snippet = e.get("snippet", "").strip()
                content_text = (
                    f"{headline} ({date}) | Signal: {signal.replace('_', ' ')} | "
                    f"Why relevant to Sonar: {why}"
                )
                if snippet:
                    content_text += f" | Article excerpt: {snippet}"
                st.session_state[sel_key].append({"type": "news", "content": content_text})
            target = content
        else:
            target = st.container()

        article_summary = e.get("article_summary", "")
        summary_html = (
            f"<div style='color:{TEXT_DIM};font-size:{TYPE['caption']};margin-bottom:10px;"
            f"line-height:1.55;font-style:italic'>{article_summary}</div>"
            if article_summary else ""
        )
        target.markdown(f"""
<div class="si-news-card">
  <div style="color:{ACCENT};font-size:{TYPE['micro']};font-weight:700;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.05em">{date}</div>
  <div style="font-weight:600;color:{TEXT};margin-bottom:8px;line-height:1.45;font-size:{TYPE['small']}">{headline}</div>
  {summary_html}
  <div style="margin-bottom:10px">
    <span style="color:{ACCENT};font-size:{TYPE['micro']};font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Why it matters to Sonar</span>
    <div style="color:{MUTED};font-size:{TYPE['caption']};margin-top:3px;line-height:1.5">{why}</div>
  </div>
  {link_html}
</div>""", unsafe_allow_html=True)


def _tab_pain(r: dict, sigs: dict, ck: str, show_email: bool, velocity_mode: bool, run_path: str):
    pain = sigs.get(AGENT_PAIN_POINTS) or {}
    score_val = pain.get("sonar_relevance_score", 0)
    section_header("Developer Pain Points",
                   subtitle=f"Score: {round(score_val, 1)}/10")

    if pain.get("summary"):
        micro_label("Summary", color=ACCENT)
        st.markdown(bullets_html(pain["summary"], color=TEXT_DIM, size="small"),
                    unsafe_allow_html=True)

    if pain.get("sonar_relevance_reason"):
        spacer("sm")
        micro_label("Why Sonar", color=ACCENT)
        st.markdown(bullets_html(pain["sonar_relevance_reason"], color=TEXT_DIM, size="small"),
                    unsafe_allow_html=True)

    if pain.get("recommended_sales_angle"):
        spacer("sm")
        angle_bullets = bullets_html(pain["recommended_sales_angle"], color=TEXT, size="small")
        st.markdown(
            f"<div style='background:{ACCENT_SOFT};border-left:3px solid {ACCENT};"
            f"padding:10px 14px;border-radius:0 8px 8px 0;margin:6px 0'>"
            f"<span style='color:{ACCENT};font-size:{TYPE['micro']};font-weight:700;"
            f"text-transform:uppercase;letter-spacing:0.08em'>Recommended Sales Angle</span>"
            f"{angle_bullets}</div>",
            unsafe_allow_html=True,
        )

    spacer("md")
    evidence = [e for e in pain.get("evidence", []) if e.get("counted_in_score")] or pain.get("evidence", [])
    if not evidence:
        if pain.get("status") == "no_data":
            st.caption("No company-linked pain signals found in public sources.")
        return

    for e in evidence:
        cat_key   = e.get("category", "")
        cat_label = _PAIN_CATEGORY_LABELS.get(cat_key, cat_key.replace("_", " ").title())
        cat_color = _PAIN_CATEGORY_COLORS.get(cat_key, MUTED)
        conf      = e.get("confidence", "—")
        ev_text   = e.get("evidence_text", "—")
        url       = e.get("source_url", "")
        title     = e.get("title", "")
        keywords  = e.get("matched_keywords", [])
        link_html = f"<a class='si-link' href='{url}' target='_blank'>SOURCE ↗</a>" if url else ""
        kw_html   = (
            "  ·  " + "  ".join(
                f"<span style='background:{ACCENT_SOFT};color:{ACCENT};padding:1px 7px;"
                f"border-radius:4px;font-size:{TYPE['micro']}'>{kw}</span>"
                for kw in keywords[:5]
            )
            if keywords else ""
        )
        ev_html = bullets_html(ev_text, color=MUTED, size="small")
        st.markdown(f"""
<div class="si-news-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    {pill_html(cat_label, cat_color)}
    <span style="color:{MUTED};font-size:{TYPE['caption']}">{conf}</span>
  </div>
  {"<div style='font-weight:600;color:" + TEXT + ";font-size:" + TYPE['small'] + ";margin-bottom:6px;line-height:1.4'>" + title + "</div>" if title else ""}
  {ev_html}
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span style="font-size:{TYPE['caption']}">{kw_html}</span>
    {link_html}
  </div>
</div>""", unsafe_allow_html=True)

    if pain.get("limitations"):
        with st.expander("⚠ Research Limitations", expanded=False):
            for lim in pain["limitations"]:
                st.caption(lim)


def _tab_people_regs(r: dict, sigs: dict, ck: str, show_email: bool, velocity_mode: bool, run_path: str):
    """ENT tab — stakeholder intelligence + regulatory impact."""
    sk = sigs.get(AGENT_STAKEHOLDER) or {}
    reg = sigs.get(AGENT_REGULATORY) or {}

    if sk.get("stakeholders"):
        section_header("Stakeholder Intelligence")
        sk_rows = [{
            "Name":                 p.get("name", ""),
            "Role":                 p.get("role", ""),
            "LinkedIn":             p.get("linkedin_url", ""),
            "Confidence":           p.get("confidence", ""),
            "Personality":          p.get("personality_display", ""),
            "Why this personality": p.get("personality_reasoning", "—"),
        } for p in sk["stakeholders"]]
        st.markdown(_html_table(
            sk_rows, link_cols={"LinkedIn"},
            col_styles={
                "LinkedIn":    "width:80px;text-align:center",
                "Confidence":  "width:80px",
                "Personality": "width:120px",
            },
        ), unsafe_allow_html=True)
        spacer("md")

    if reg:
        section_header("Regulatory Impact",
                       subtitle=f"Score: {round(reg.get('sonar_relevance_score', 0), 2)}/10")
        all_evidence = [e for e in reg.get("evidence", []) if e.get("counted_in_score")] or reg.get("evidence", [])
        evidence = [e for e in all_evidence if e.get("source_url", "").strip()]
        hidden_count = len(all_evidence) - len(evidence)
        sel_key = f"selected_items_{ck}"

        if not evidence:
            st.caption("No regulatory evidence found.")
        else:
            for idx, e in enumerate(evidence):
                regulation = e.get("regulation", "—") or "—"
                finding    = e.get("evidence_text", "—")
                relevance  = _REG_RELEVANCE.get(e.get("type", ""), e.get("type", "—").replace("_", " ").title())
                url        = e.get("source_url", "")
                conf       = e.get("confidence", "—")
                link_html  = f"<a class='si-link' href='{url}' target='_blank'>VIEW ↗</a>" if url else ""

                if show_email:
                    cb, content = st.columns([0.06, 1])
                    cb_state = cb.checkbox("Include in email", key=f"eml_{ck}_reg_{idx}", label_visibility="collapsed")
                    if cb_state:
                        st.session_state[sel_key].append({
                            "type": "regulatory", "content": f"{regulation}: {finding}",
                        })
                    target = content
                else:
                    target = st.container()

                target.markdown(f"""
<div class="si-row-card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span style="font-weight:700;color:{TEXT};font-size:{TYPE['small']}">{regulation}</span>
    <span style="color:{MUTED};font-size:{TYPE['caption']}">{conf}</span>
  </div>
  <div style="color:{MUTED};font-size:{TYPE['caption']};margin-top:5px;line-height:1.45">{finding}</div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
    <span style="color:{ACCENT};font-size:{TYPE['caption']};font-weight:600">{relevance}</span>
    {link_html}
  </div>
</div>""", unsafe_allow_html=True)
            if hidden_count > 0:
                st.caption(f"ℹ {hidden_count} industry-mapping finding(s) not shown — no direct source URL available.")


def _tab_email(r: dict, sigs: dict, ck: str, show_email: bool, velocity_mode: bool, run_path: str):
    selected_items = st.session_state.get(f"selected_items_{ck}", [])
    _render_email_panel(r, sigs, selected_items, ck, velocity_mode=velocity_mode, run_path=run_path)


# ── Advisor persistence ─────────────────────────────────────────────────────

def _save_advisor_to_run(run_path: str, company: str, adv_result: dict):
    """Persist a freshly-run advisor result back into the saved run JSON."""
    if not run_path:
        return
    try:
        from ui.results_store import load_run
        run = load_run(run_path)
        for res in run.get("results", []):
            if res["company"] == company:
                res["signals"][AGENT_ADVISOR] = adv_result
                break
        with open(run_path, "w", encoding="utf-8") as f:
            json.dump(run, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ── Email panel — side-by-side, editable, tone presets ─────────────────────

def _render_email_panel(r: dict, sigs: dict, selected_items: list, ck: str,
                        velocity_mode: bool = False, run_path: str = ""):
    section_header("Draft Outreach Email",
                   subtitle="Pick a tone, edit freely, copy when ready.")

    adv_result = st.session_state.get(f"adv_result_{ck}", {})

    advisor_selected_items: list[dict] = []
    strategy_note = ""

    if not adv_result:
        st.markdown(
            f"<div style='background:rgba(148,163,184,0.06);border:1px solid {BORDER};"
            f"border-radius:{RADIUS['md']}px;padding:14px 18px;margin-bottom:14px'>"
            f"<span style='color:{MUTED};font-size:{TYPE['small']}'>"
            f"Outreach Suggest was not included in this research run. "
            f"Enable <strong>Outreach Suggest</strong> on the Home page before running, "
            f"or click <strong>Run Advisor Now</strong> below.</span></div>",
            unsafe_allow_html=True,
        )
        if st.button("Run Advisor Now", key=f"adv_run_now_{ck}", type="secondary"):
            from agents.advisor.agent import SignalAdvisorAgent
            with st.spinner("Analysing signals…"):
                adv_result = SignalAdvisorAgent().analyse(r["company"], sigs)
            st.session_state[f"adv_result_{ck}"] = adv_result
            _save_advisor_to_run(run_path, r["company"], adv_result)
            st.rerun()

    if adv_result:
        if adv_result.get("error") and not adv_result.get("hook_title"):
            st.warning(f"Advisor could not analyse signals: {adv_result['error']}")
        else:
            strategy_note  = adv_result.get("strategy_note", "")
            suggested      = adv_result.get("suggested_signals", [])

            if suggested:
                micro_label("Advisor-Suggested Signals", color=MUTED)
                spacer("xs")
                for idx, sig in enumerate(suggested):
                    adv_key = f"adv_sig_{ck}_{idx}"
                    if adv_key not in st.session_state:
                        st.session_state[adv_key] = True

                    cb_col, card_col = st.columns([0.05, 0.95])
                    cb_col.checkbox("Use this signal", key=adv_key, label_visibility="collapsed")
                    if st.session_state.get(adv_key):
                        advisor_selected_items.append({
                            "type":    sig.get("type", "signal"),
                            "content": sig.get("content", ""),
                        })

                    sig_type  = sig.get("type", "")
                    type_color = SIGNAL_COLORS.get(sig_type, MUTED)
                    card_col.markdown(
                        f"<div class='si-row-card'>"
                        f"<div style='display:flex;align-items:flex-start;gap:10px'>"
                        f"{pill_html(sig_type.replace('_', ' '), type_color)}"
                        f"<div>"
                        f"<div style='color:{TEXT};font-size:{TYPE['small']};font-weight:600;"
                        f"line-height:1.35'>{sig.get('label', '')}</div>"
                        f"<div style='color:{MUTED};font-size:{TYPE['caption']};margin-top:3px;"
                        f"line-height:1.4'>{sig.get('why', '')}</div>"
                        f"</div></div></div>",
                        unsafe_allow_html=True,
                    )

                col_note, col_rerun = st.columns([3, 1])
                col_note.caption("Untick any signal you want to remove.")
                if col_rerun.button("Re-analyse", key=f"adv_rerun_{ck}", type="secondary"):
                    from agents.advisor.agent import SignalAdvisorAgent
                    with st.spinner("Re-analysing signals…"):
                        adv_result = SignalAdvisorAgent().analyse(r["company"], sigs)
                    st.session_state[f"adv_result_{ck}"] = adv_result
                    _save_advisor_to_run(run_path, r["company"], adv_result)
                    st.rerun()

    effective_selected = (
        advisor_selected_items
        if (adv_result and not (adv_result.get("error") and not adv_result.get("hook_title")))
        else selected_items
    )

    spacer("md")

    # ── Two-column layout: controls | preview ───────────────────────────
    left, right = st.columns([1, 1.15], gap="large")

    with left:
        micro_label("Sender & Target")
        sender_name = st.text_input(
            "Your name (sign-off)", key=f"eml_sender_{ck}",
            placeholder="e.g. Sarah Lim",
        )

        if velocity_mode:
            col_name, col_role = st.columns(2)
            target_name = col_name.text_input(
                "Contact name", key=f"eml_name_{ck}", placeholder="e.g. Thomas Müller"
            )
            target_role = col_role.text_input(
                "Contact role", key=f"eml_role_{ck}", placeholder="e.g. Head of Engineering"
            )
            personality = ["Unknown"]
        else:
            stakeholders = (sigs.get(AGENT_STAKEHOLDER, {}) or {}).get("stakeholders", [])
            target_name = ""
            target_role = ""

            if stakeholders:
                options = [f"{p['name']}  —  {p['role']}" for p in stakeholders] + ["Enter manually"]
                choice = st.selectbox("Target stakeholder", options, key=f"eml_target_{ck}")
                if choice == "Enter manually":
                    target_name = st.text_input("Contact name", key=f"eml_name_{ck}",
                                                placeholder="e.g. Thomas Müller")
                    target_role = st.text_input("Contact role", key=f"eml_role_{ck}",
                                                placeholder="e.g. Head of Engineering")
                else:
                    idx = options.index(choice)
                    target_name = stakeholders[idx]["name"]
                    target_role = stakeholders[idx]["role"]
                    inferred = stakeholders[idx].get("personality_display", "")
                    if inferred:
                        st.caption(f"Inferred personality: **{inferred}**")
            else:
                st.caption("No stakeholders found — enter manually.")
                target_name = st.text_input("Contact name", key=f"eml_name_{ck}",
                                            placeholder="e.g. Thomas Müller")
                target_role = st.text_input("Contact role", key=f"eml_role_{ck}",
                                            placeholder="e.g. Head of Engineering")

            spacer("sm")
            micro_label("Personality colour")
            default_personality = "Unknown"
            if stakeholders:
                choice_val = st.session_state.get(f"eml_target_{ck}", "")
                if choice_val and choice_val != "Enter manually":
                    try:
                        si = [f"{p['name']}  —  {p['role']}" for p in stakeholders].index(choice_val)
                        raw = stakeholders[si].get("personality_display", "")
                        for c in ["Red", "Blue", "Green", "Yellow"]:
                            if c.lower() in raw.lower():
                                default_personality = c
                                break
                    except (ValueError, IndexError):
                        pass

            pers_cols = st.columns(len(_PERSONALITY_OPTIONS))
            personality = []
            for col, opt in zip(pers_cols, _PERSONALITY_OPTIONS):
                with col:
                    checked = st.checkbox(
                        opt,
                        value=(opt == default_personality),
                        key=f"eml_pers_{ck}_{opt}",
                    )
                    if checked:
                        personality.append(opt)
            if not personality:
                personality = ["Unknown"]

            pers_color = PERSONALITY_COLORS.get(personality[0], MUTED)
            desc_text = "  ·  ".join(_PERSONALITY_DESCS.get(p, "") for p in personality)
            st.markdown(
                f"<span style='color:{pers_color};font-size:{TYPE['caption']}'>"
                f"{desc_text}</span>",
                unsafe_allow_html=True,
            )

        spacer("md")
        micro_label("Tone preset")
        st.caption("Click a preset before regenerating to nudge the style.")
        chosen_tone_key = f"eml_tone_{ck}"
        if chosen_tone_key not in st.session_state:
            st.session_state[chosen_tone_key] = ""
        preset_names = list(_TONE_PRESETS.keys())
        for row_names in [preset_names[:2], preset_names[2:]]:
            tone_cols = st.columns(len(row_names))
            for col, name in zip(tone_cols, row_names):
                with col:
                    active = st.session_state[chosen_tone_key] == name
                    if st.button(
                        ("✓ " + name) if active else name,
                        key=f"eml_tone_btn_{ck}_{name}",
                        type=("primary" if active else "secondary"),
                        use_container_width=True,
                    ):
                        st.session_state[chosen_tone_key] = "" if active else name
                        st.rerun()

        spacer("md")
        can_generate = bool((target_name or "").strip())
        profile = sigs.get(AGENT_PROFILE, {})
        company_context = profile.get("snapshot", {}) if profile else {}
        company_position = sigs.get(AGENT_POSITION, {}).get("position_label", "—") if sigs.get(AGENT_POSITION) else "—"

        if st.button(
            "Generate Email Draft",
            type="primary",
            key=f"eml_btn_{ck}",
            disabled=not can_generate,
            use_container_width=True,
        ):
            from agents.email.agent import EmailDraftAgent
            tone_hint = _TONE_PRESETS.get(st.session_state.get(chosen_tone_key, ""), "")
            note = (strategy_note + "\n\n" + tone_hint).strip() if tone_hint else strategy_note
            with st.spinner("Drafting email…"):
                result = EmailDraftAgent().draft(
                    company=r["company"],
                    target_name=target_name,
                    target_role=target_role,
                    personality=personality,
                    selected_items=effective_selected,
                    company_context=company_context,
                    company_position=company_position,
                    strategy_note=note,
                )
            st.session_state[f"eml_result_{ck}"] = result
            st.session_state[f"eml_params_{ck}"] = dict(
                company=r["company"], target_name=target_name, target_role=target_role,
                personality=personality, selected_items=effective_selected,
                company_context=company_context, company_position=company_position,
                strategy_note=strategy_note,
            )
            # Seed editable copies
            st.session_state[f"eml_edit_subject_{ck}"] = result.get("subject", "")
            st.session_state[f"eml_edit_body_{ck}"]    = result.get("body", "")
            st.rerun()

        result_existing = st.session_state.get(f"eml_result_{ck}")
        if result_existing:
            rcol1, rcol2 = st.columns(2)
            with rcol1:
                if st.button("Regenerate", key=f"eml_regen_{ck}", use_container_width=True):
                    params = st.session_state.get(f"eml_params_{ck}", {})
                    if params:
                        from agents.email.agent import EmailDraftAgent
                        tone_hint = _TONE_PRESETS.get(st.session_state.get(chosen_tone_key, ""), "")
                        if tone_hint:
                            params = {**params, "strategy_note":
                                      (params.get("strategy_note", "") + "\n\n" + tone_hint).strip()}
                        with st.spinner("Regenerating…"):
                            new_result = EmailDraftAgent().draft(**params)
                        st.session_state[f"eml_result_{ck}"] = new_result
                        st.session_state[f"eml_edit_subject_{ck}"] = new_result.get("subject", "")
                        st.session_state[f"eml_edit_body_{ck}"]    = new_result.get("body", "")
                        st.rerun()
            with rcol2:
                if st.button("Different Hook", key=f"eml_diffhook_{ck}", use_container_width=True):
                    params = st.session_state.get(f"eml_params_{ck}", {})
                    if params:
                        from agents.email.agent import EmailDraftAgent
                        with st.spinner("Finding different angle…"):
                            new_result = EmailDraftAgent().draft(
                                **params, avoid_hook=result_existing.get("hook_title", "")
                            )
                        st.session_state[f"eml_result_{ck}"] = new_result
                        st.session_state[f"eml_edit_subject_{ck}"] = new_result.get("subject", "")
                        st.session_state[f"eml_edit_body_{ck}"]    = new_result.get("body", "")
                        st.rerun()

    with right:
        result = st.session_state.get(f"eml_result_{ck}")
        if not result:
            st.markdown(
                f"<div style='background:{CARD};border:1px dashed {BORDER};"
                f"border-radius:{RADIUS['md']}px;padding:40px 20px;text-align:center;"
                f"color:{MUTED};font-size:{TYPE['small']}'>"
                f"<div style='font-size:1.4rem;margin-bottom:8px'>✉</div>"
                f"Fill in the fields and click <strong style='color:{ACCENT}'>Generate</strong> "
                f"to draft an email.</div>",
                unsafe_allow_html=True,
            )
            return

        if result.get("error") and not result.get("body"):
            st.error(f"Draft failed: {result['error']}")
            return

        if result.get("length_warning"):
            st.warning(result["length_warning"])

        sender = st.session_state.get(f"eml_sender_{ck}", "").strip() or "[Sender Name]"

        micro_label("Subject")
        subject_val = st.text_input(
            "Subject",
            key=f"eml_edit_subject_{ck}",
            label_visibility="collapsed",
        )

        micro_label("Body")
        body_val = st.text_area(
            "Body",
            key=f"eml_edit_body_{ck}",
            height=320,
            label_visibility="collapsed",
        )

        # Substitute sender placeholder for preview/copy
        display_body = (body_val or "").replace("[Sender Name]", sender)
        if not any(w in display_body.lower() for w in ("best regards", "kind regards", "regards,")):
            display_body = display_body.rstrip() + f"\n\nBest regards,\n{sender}"

        full_email_json = json.dumps(f"Subject: {subject_val}\n\n{display_body}")
        # Compact preview / copy widget
        components.html(f"""
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: transparent; font-family: 'Inter', -apple-system, sans-serif; }}
  .card {{
    background:{CARD}; border:1px solid {BORDER}; border-radius:{RADIUS['md']}px;
    padding:14px 16px; position:relative;
  }}
  .copy-btn {{
    background:{ACCENT}; color:#0b1220; border:none;
    padding:7px 14px; border-radius:{RADIUS['sm']}px;
    font-weight:700; cursor:pointer; font-size:{TYPE['caption']};
    font-family:inherit; transition:background 0.15s ease;
  }}
  .copy-btn:hover {{ background:{ACCENT_80}; }}
  .lbl {{ color:{MUTED}; font-size:{TYPE['micro']}; text-transform:uppercase; letter-spacing:0.06em; }}
  .val {{ color:{TEXT}; font-size:{TYPE['small']}; font-weight:600; }}
  .meta {{ display:flex; align-items:baseline; gap:10px; }}
</style>
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <div class="meta"><span class="lbl">To</span><span class="val">{(r.get('company',''))}</span></div>
      <div class="meta" style="margin-top:4px"><span class="lbl">Length</span><span class="val">{len(display_body.split())} words · {len(display_body)} chars</span></div>
    </div>
    <button class="copy-btn" id="cb" onclick="
      navigator.clipboard.writeText({full_email_json}).then(function(){{
        var b=document.getElementById('cb');
        b.innerHTML='✓ Copied!';
        setTimeout(function(){{ b.innerHTML='⧉ Copy email'; }},1800);
      }});
    ">⧉ Copy email</button>
  </div>
</div>
""", height=90)
