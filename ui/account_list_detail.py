import streamlit as st
import pandas as pd
from ui.results_store import load_run
from agents.director import (
    AGENT_TECH_STACK, AGENT_HIRING, AGENT_NEWS,
    AGENT_POSITION, AGENT_REGULATORY,
)

if "selected_run_path" not in st.session_state:
    st.warning("No account list selected.")
    if st.button("Go to ENT Account Lists"):
        st.switch_page("ui/ent_accounts.py")
    st.stop()

data = load_run(st.session_state["selected_run_path"])
meta = data["metadata"]
results = data["results"]

# ── Header ────────────────────────────────────────────────────────────────────
role = meta.get("role", "")
back_page = "ui/ent_accounts.py" if "Territory" in role else "ui/velocity_accounts.py"
if st.button("← Back to Account Lists"):
    st.switch_page(back_page)

st.title(meta.get("source_filename", "Account List"))
st.caption(f"{meta.get('display_date', meta.get('date', '')[:16].replace('T', ' '))}  ·  {meta['company_count']} companies  ·  {role}")
st.markdown("---")

# ── Ranked table ──────────────────────────────────────────────────────────────
st.subheader("Ranked by Propensity to Buy")

summary_rows = []
for r in results:
    row = {
        "Rank":    r["rank"],
        "Company": r["company"],
        "Domain":  r.get("domain", ""),
        "Score":   round(r["total_score"], 2),
    }
    ts = r["signals"].get(AGENT_TECH_STACK, {})
    if ts:
        row["Languages"] = ", ".join(l["name"] for l in ts.get("languages", []))
        row["CI/CD"]     = ", ".join(l["name"] for l in ts.get("cicd_tools", []))
        row["Cloud"]     = ", ".join(l["name"] for l in ts.get("cloud", []))

    pos = r["signals"].get(AGENT_POSITION, {})
    if pos:
        row["Position"] = pos.get("position_label", "")

    reg = r["signals"].get(AGENT_REGULATORY, {})
    if reg:
        row["Regulatory Score"] = round(reg.get("sonar_relevance_score", 0), 2)

    summary_rows.append(row)

st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
st.markdown("---")

# ── Per-account view buttons ──────────────────────────────────────────────────
st.subheader("Account Detail")
for i, r in enumerate(results):
    col1, col2, col3 = st.columns([1, 5, 2])
    col1.write(f"#{r['rank']}")
    col2.write(f"**{r['company']}** — Score: {round(r['total_score'], 2)}")
    if col3.button("View Findings", key=f"view_{i}"):
        st.session_state["selected_account_idx"] = i
        st.switch_page("ui/account_detail.py")
