import streamlit as st
import pandas as pd
from ui.results_store import load_run
from agents.director import (
    AGENT_TECH_STACK, AGENT_HIRING, AGENT_NEWS,
    AGENT_POSITION, AGENT_REGULATORY, AGENT_PROFILE, AGENT_STAKEHOLDER,
)

if "selected_run_path" not in st.session_state or "selected_account_idx" not in st.session_state:
    st.warning("No account selected.")
    if st.button("Go to ENT Account Lists"):
        st.switch_page("ui/ent_accounts.py")
    st.stop()

data = load_run(st.session_state["selected_run_path"])
results = data["results"]
idx = st.session_state["selected_account_idx"]
r = results[idx]
sigs = r["signals"]

# ── Header ────────────────────────────────────────────────────────────────────
if st.button("← Back to Account List"):
    st.switch_page("ui/account_list_detail.py")

st.title(r["company"])
st.caption(f"Rank #{r['rank']}  ·  Propensity Score: {round(r['total_score'], 2)}  ·  Domain: {r.get('domain', '—')}")
st.markdown("---")

# ── Company Profile ───────────────────────────────────────────────────────────
profile = sigs.get(AGENT_PROFILE)
if profile and profile.get("snapshot"):
    snap = profile["snapshot"]
    st.subheader("Company Profile")
    for label, key in [
        ("What they do",     "what_they_do"),
        ("Who they sell to", "who_they_sell_to"),
        ("Business model",   "business_model"),
        ("Key acquisitions", "key_acquisition"),
        ("AI posture",       "ai_posture"),
    ]:
        val = snap.get(key, "")
        if val:
            st.markdown(f"**{label}:** {val}")
    st.markdown("")

# ── Tech Stack ────────────────────────────────────────────────────────────────
ts = sigs.get(AGENT_TECH_STACK)
if ts:
    st.subheader("Tech Stack")
    score_val = ts.get("sonar_relevance_score", 0)
    confidence = ts.get("confidence", "—")
    st.markdown(f"Score: **{score_val}/10**  |  Confidence: **{confidence}**")
    summary = ts.get("summary", "")
    if summary:
        st.caption(summary)

    ev_lookup = {e["id"]: e for e in ts.get("evidence", [])}
    ts_rows = []
    for category, items in [
        ("Language",       ts.get("languages", [])),
        ("CI/CD",          ts.get("cicd_tools", [])),
        ("Cloud / DevOps", ts.get("cloud", [])),
        ("Security Tool",  ts.get("security_tools", [])),
    ]:
        for item in items:
            ev_ids = item.get("evidence_ids", [])
            first_ev = ev_lookup.get(ev_ids[0]) if ev_ids else None
            ts_rows.append({
                "Category":   category,
                "Finding":    item.get("name", "—"),
                "Evidence":   first_ev["evidence_text"] if first_ev else "—",
                "Source":     first_ev["repo_url"] if first_ev else "—",
                "Confidence": item.get("confidence", "—"),
            })
    if ts_rows:
        st.dataframe(pd.DataFrame(ts_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No tech stack signals detected.")
    st.markdown("")

# ── Hiring Signals ────────────────────────────────────────────────────────────
hiring = sigs.get(AGENT_HIRING)
if hiring:
    st.subheader("Hiring Signals")
    score_val = hiring.get("sonar_relevance_score", 0)
    confidence = hiring.get("confidence", "—")
    st.markdown(f"Score: **{score_val}/10**  |  Confidence: **{confidence}**")
    summary = hiring.get("summary", "")
    if summary:
        st.caption(summary)

    _CATEGORY_LABELS = {
        "DevSecOps_AppSec":       "DevSecOps / AppSec",
        "DevOps_Platform":        "DevOps / Platform",
        "Software_Engineering":   "Software Engineering",
        "Security":               "Security",
        "Cloud_Infrastructure":   "Cloud / Infrastructure",
        "Language_Signal":        "Language Signal",
    }

    evidence = [e for e in hiring.get("evidence", []) if e.get("counted_in_score")]
    if not evidence:
        evidence = hiring.get("evidence", [])

    if evidence:
        # Count postings per (value, type) to get postings_found
        from collections import Counter
        counts = Counter((e.get("value", ""), e.get("type", "")) for e in evidence)
        seen = set()
        h_rows = []
        for e in evidence:
            key = (e.get("value", ""), e.get("type", ""))
            if key in seen:
                continue
            seen.add(key)
            h_rows.append({
                "Job Title":       e.get("value", "—"),
                "Category":        _CATEGORY_LABELS.get(e.get("type", ""), e.get("type", "—")),
                "Postings Found":  f"{counts[key]}+",
                "Source":          e.get("source_url", ""),
                "Confidence":      e.get("confidence", "—"),
            })
        st.dataframe(
            pd.DataFrame(h_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Source": st.column_config.LinkColumn("Source", display_text="Open ↗"),
            },
        )
    else:
        st.caption("No hiring signals detected.")
    st.markdown("")

# ── Public News ───────────────────────────────────────────────────────────────
news = sigs.get(AGENT_NEWS)
if news:
    st.subheader("Public News")
    score_val = news.get("sonar_relevance_score", 0)
    confidence = news.get("confidence", "—")
    st.markdown(f"Score: **{score_val}/10**  |  Confidence: **{confidence}**")
    summary = news.get("summary", "")
    if summary:
        st.caption(summary)

    _WHY_IT_MATTERS = {
        "security_incident":      "Active security incident — urgent pressure to improve code security posture",
        "compliance_regulatory":  "Regulatory requirement — compliance deadlines drive SAST/code quality investment",
        "cloud_ai_initiative":    "Cloud/AI expansion means more code being written — quality gate needs grow",
        "product_launch":         "New product launch signals active development — potential quality gaps",
        "leadership_change":      "Leadership change often triggers technology stack reviews",
        "acquisition":            "M&A activity creates code integration challenges across teams",
        "hiring_wave":            "Hiring surge indicates growing dev teams — code quality standards need to scale",
    }

    evidence = [e for e in news.get("evidence", []) if e.get("counted_in_score")]
    if not evidence:
        evidence = news.get("evidence", [])

    if evidence:
        n_rows = []
        for e in evidence:
            signal = e.get("signal_type", "")
            n_rows.append({
                "Date":            e.get("published_date", "—") or "—",
                "Headline":        e.get("title", "—"),
                "Why it matters":  _WHY_IT_MATTERS.get(signal, signal.replace("_", " ").title()),
                "Source":          e.get("url", ""),
            })
        df_news = pd.DataFrame(n_rows)
        st.dataframe(
            df_news,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Source": st.column_config.LinkColumn("Source", display_text="Open ↗"),
            },
        )
    else:
        st.caption("No news evidence found.")
    st.markdown("")

# ── Company Position ──────────────────────────────────────────────────────────
pos = sigs.get(AGENT_POSITION)
if pos:
    st.subheader("Company Position")
    label   = pos.get("position_label", "—")
    conf    = pos.get("confidence", "—")
    score   = pos.get("classification_score", 0)
    st.markdown(f"**{label}**  |  Confidence: {conf}  |  Score: {score}/10")
    summary = pos.get("summary", "")
    if summary:
        st.write(summary)
    angle = pos.get("recommended_sales_angle", "")
    if angle:
        st.info(f"Sales angle: {angle}")
    st.markdown("")

# ── Regulatory Impact ─────────────────────────────────────────────────────────
reg = sigs.get(AGENT_REGULATORY)
if reg:
    st.subheader("Regulatory Impact")
    score_val = round(reg.get("sonar_relevance_score", 0), 2)
    conf = reg.get("confidence", "—")
    st.markdown(f"Score: **{score_val}/10**  |  Confidence: **{conf}**")
    summary = reg.get("summary", "")
    if summary:
        st.caption(summary)

    _REG_RELEVANCE = {
        "active_fine_lawsuit":           "Active enforcement — urgent compliance need",
        "specific_regulation_applies":   "Direct regulation — Sonar addresses requirement",
        "compliance_audit":              "Audit activity — code quality under scrutiny",
        "regulated_industry":            "Regulated industry — compliance baseline expected",
        "regional_regulator_relevance":  "Regional regulator active in this space",
        "general_regulatory_mention":    "General regulatory context",
    }

    evidence = [e for e in reg.get("evidence", []) if e.get("counted_in_score")]
    if not evidence:
        evidence = reg.get("evidence", [])

    if evidence:
        reg_rows = []
        for e in evidence:
            reg_rows.append({
                "Regulation":      e.get("regulation", "—") or "—",
                "Finding":         e.get("evidence_text", "—"),
                "Sonar Relevance": _REG_RELEVANCE.get(e.get("type", ""), e.get("type", "—").replace("_", " ").title()),
                "Source":          e.get("source_url", ""),
                "Confidence":      e.get("confidence", "—"),
            })
        st.dataframe(
            pd.DataFrame(reg_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Source": st.column_config.LinkColumn("Source", display_text="Open ↗"),
            },
        )
    else:
        st.caption("No regulatory evidence found.")
    st.markdown("")

# ── Stakeholders ──────────────────────────────────────────────────────────────
sk = sigs.get(AGENT_STAKEHOLDER)
if sk and sk.get("stakeholders"):
    st.subheader("Stakeholder Intelligence")
    sk_rows = []
    for p in sk["stakeholders"]:
        sk_rows.append({
            "Role":                 p.get("role", ""),
            "Name":                 p.get("name", ""),
            "LinkedIn":             p.get("linkedin_url", ""),
            "Confidence":           p.get("confidence", ""),
            "Personality":          p.get("personality_display", ""),
            "Why this personality": p.get("personality_reasoning", "—"),
        })
    st.dataframe(
        pd.DataFrame(sk_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "LinkedIn": st.column_config.LinkColumn("LinkedIn", display_text="View ↗"),
        },
    )
    st.markdown("")
