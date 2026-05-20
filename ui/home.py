import os
import time
import streamlit as st
import pandas as pd
from ui.results_store import (
    begin_run,
    finalize_run,
    find_partial_run,
    load_partial_run,
    save_checkpoint,
)
from ui.theme import inject_theme
from ui.design import (
    ACCENT, ACCENT_SOFT, BORDER, CARD, DANGER, INFO, MUTED, RADIUS, SPACE,
    TEXT, TEXT_DIM, TYPE, WARN,
)
from ui.components import (
    metric_card, micro_label, pill_html, score_bar_html, section_header,
    spacer, status_pill,
)
from agents.discovery.agent import CompanyDiscoveryAgent

inject_theme()

from agents.director import (
    DirectorAgent,
    ROLE_TERRITORY_MANAGER,
    ROLE_VELOCITY,
    AGENT_TECH_STACK,
    AGENT_HIRING,
    AGENT_NEWS,
    AGENT_POSITION,
    AGENT_REGULATORY,
    AGENT_PROFILE,
    AGENT_STAKEHOLDER,
    AGENT_PAIN_POINTS,
    AGENT_ADVISOR,
)

st.markdown("""
<div style="display:flex;align-items:center;gap:14px;margin-bottom:28px">
  <div style="background:#00d4aa;width:36px;height:36px;border-radius:9px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
    <span style="color:#050a14;font-weight:900;font-size:1.1rem">S</span>
  </div>
  <div>
    <div style="color:#f8fafc;font-size:1.35rem;font-weight:700;line-height:1.2">Sonar AI Sales Agent</div>
    <div style="color:#94a3b8;font-size:0.8rem">Multi-Role Intelligence Pipeline</div>
  </div>
</div>
""", unsafe_allow_html=True)

col_left, col_right = st.columns([1, 1.4], gap="large")

with col_left:
    st.subheader("Configuration")

    role = st.radio(
        "SELECT WORKSTREAM",
        options=[ROLE_TERRITORY_MANAGER, ROLE_VELOCITY],
        horizontal=False,
    )

    st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)
    st.subheader("Target Accounts")

    df = None
    uploaded_file = None

    # Velocity Mode A inputs (declared here so they're in scope for the run block below)
    vel_countries_input = ""
    vel_industries_input = ""
    vel_count = 20
    vel_mode_a = False

    if role == ROLE_TERRITORY_MANAGER:
        st.caption("Upload a CSV or Excel file with 100–500 target accounts.")
        uploaded_file = st.file_uploader("ACCOUNT LIST (CSV / XLSX)", type=["csv", "xlsx"], key="ent_upload")
        if uploaded_file:
            df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
            st.success(f"{len(df)} accounts loaded.")
            st.dataframe(df.head(5), use_container_width=True)
            # Store ENT accounts for Velocity dedup
            ent_set: set[str] = set()
            for _, row in df.iterrows():
                company = (
                    row.get("company") or row.get("Company")
                    or row.get("Account Name", "")
                )
                if company:
                    ent_set.add(str(company).strip().lower())
                domain = (
                    row.get("domain") or row.get("Domain")
                    or row.get("Website", "")
                )
                if domain:
                    ent_set.add(str(domain).strip().lower())
            st.session_state["ent_company_set"] = ent_set
    else:
        list_option = st.radio(
            "LIST SOURCE",
            options=["Upload my own Velocity list", "Create a list (agent curates from web)"],
            key="vel_source",
        )
        if list_option == "Upload my own Velocity list":
            uploaded_file = st.file_uploader("VELOCITY LIST (CSV / XLSX)", type=["csv", "xlsx"], key="vel_upload")
            if uploaded_file:
                df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
                st.success(f"{len(df)} accounts loaded.")
                st.dataframe(df.head(5), use_container_width=True)
        else:
            vel_mode_a = True
            st.caption("Agent will search the web for mid-market companies matching your criteria.")
            st.caption("Separate multiple values with commas.")
            vel_countries_input = st.text_input(
                "COUNTRIES",
                placeholder="e.g. Singapore, Malaysia, Indonesia",
                key="vel_countries",
            )
            vel_industries_input = st.text_input(
                "INDUSTRIES",
                placeholder="e.g. Finance, Healthcare, Technology",
                key="vel_industries",
            )
            vel_count = st.number_input(
                "NUMBER OF ACCOUNTS",
                min_value=5,
                max_value=100,
                value=20,
                step=5,
                key="vel_count",
            )

with col_right:
    st.subheader("Intelligence Agents")
    st.caption("Select the signals you wish to extract.")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown(
            "<span style='color:#94a3b8;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em'>Signal Agents</span>",
            unsafe_allow_html=True,
        )
        run_tech    = st.checkbox("Tech Stack",     value=True, key="cb_tech")
        run_hiring  = st.checkbox("Hiring Signals", value=True, key="cb_hiring")
        run_news    = st.checkbox("Public News",    value=True, key="cb_news")

        st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
        st.markdown(
            "<span style='color:#94a3b8;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em'>Context Agents</span>",
            unsafe_allow_html=True,
        )
        run_profile = st.checkbox("Company Profile", value=True, key="cb_profile")

    with c2:
        st.markdown(
            "<span style='color:#94a3b8;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em'>Synthesis Agents</span>",
            unsafe_allow_html=True,
        )
        run_position = st.checkbox(
            "Company Position",
            value=True,
            key="cb_position",
            help="Requires Tech Stack, Hiring, or News to be meaningful.",
        )
        run_advisor = st.checkbox(
            "Outreach Suggest",
            value=True,
            key="cb_advisor",
            help="Reads all researched signals and recommends the strongest email hook. Always runs last.",
        )

        if role == ROLE_TERRITORY_MANAGER:
            st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
            st.markdown(
                "<span style='color:#94a3b8;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em'>ENT Only</span>",
                unsafe_allow_html=True,
            )
            run_reg   = st.checkbox("Regulatory Impact",        value=True, key="cb_reg")
            run_stake = st.checkbox("Stakeholder Intelligence", value=True, key="cb_stake",
                                    help="Finds technical leadership and infers personality colour. Slowest agent.")
            run_pain  = False
        else:
            run_reg   = False
            run_stake = False
            st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
            st.markdown(
                "<span style='color:#94a3b8;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em'>Velocity Only</span>",
                unsafe_allow_html=True,
            )
            run_pain = st.checkbox("Developer Pain Points", value=True, key="cb_pain",
                                   help="Searches public sources for company-linked developer pain signals relevant to Sonar.")

    agents_to_run: set[str] = set()
    if run_tech:     agents_to_run.add(AGENT_TECH_STACK)
    if run_hiring:   agents_to_run.add(AGENT_HIRING)
    if run_news:     agents_to_run.add(AGENT_NEWS)
    if run_profile:  agents_to_run.add(AGENT_PROFILE)
    if run_position: agents_to_run.add(AGENT_POSITION)
    if run_reg:      agents_to_run.add(AGENT_REGULATORY)
    if run_stake:    agents_to_run.add(AGENT_STAKEHOLDER)
    if run_pain:     agents_to_run.add(AGENT_PAIN_POINTS)
    if run_advisor:  agents_to_run.add(AGENT_ADVISOR)

    if not agents_to_run:
        st.warning("Select at least one agent to run.")

    st.markdown("<div style='margin-top:32px'></div>", unsafe_allow_html=True)

    mode_a_ready = vel_mode_a and bool(vel_countries_input.strip()) and bool(vel_industries_input.strip())

    # ── Compute a likely src_name now so we can detect a partial run ─────
    _likely_src = ""
    if vel_mode_a and mode_a_ready:
        _c = [c.strip() for c in vel_countries_input.split(",") if c.strip()]
        _i = [c.strip() for c in vel_industries_input.split(",") if c.strip()]
        _likely_src = f"agent_curated_{'+'.join(_c)}_{'+'.join(_i)}"
    elif df is not None and uploaded_file is not None:
        _likely_src = uploaded_file.name

    partial_path = find_partial_run(role, _likely_src) if _likely_src else None

    # ── Resume banner (only when a matching partial is present) ──────────
    resume_choice_key = "resume_choice"
    if partial_path:
        try:
            partial_results, partial_meta = load_partial_run(partial_path)
        except Exception:
            partial_results, partial_meta = [], {}
        n_done = len(partial_results)
        prior_date = (partial_meta or {}).get("date", "")[:16].replace("T", " ")
        spacer("md")
        st.markdown(
            f"<div style='background:{ACCENT_SOFT};border:1px solid {ACCENT}55;"
            f"border-radius:{RADIUS['md']}px;padding:14px 18px'>"
            f"<div style='color:{ACCENT};font-size:{TYPE['micro']};font-weight:700;"
            f"text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px'>"
            f"⏸ Partial run detected</div>"
            f"<div style='color:{TEXT};font-size:{TYPE['small']};line-height:1.5'>"
            f"<strong style='color:{ACCENT}'>{n_done}</strong> account(s) already analysed "
            f"from this list on <strong style='color:{ACCENT}'>{prior_date or 'an earlier session'}</strong>. "
            f"Choose how to proceed:</div></div>",
            unsafe_allow_html=True,
        )
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("▶ Resume", key="rb_resume", type="primary", use_container_width=True):
                st.session_state[resume_choice_key] = "resume"
        with b2:
            if st.button("✕ Start fresh", key="rb_fresh", type="secondary", use_container_width=True):
                try:
                    os.remove(partial_path)
                except OSError:
                    pass
                st.session_state[resume_choice_key] = "fresh"
                st.rerun()
        with b3:
            if st.button("👁 View partial", key="rb_view", type="secondary", use_container_width=True):
                tabs_key = "ent_tabs" if "Territory" in role else "vel_tabs"
                st.session_state.setdefault(tabs_key, [])
                st.session_state[tabs_key].append({
                    "type": "run", "path": partial_path, "label": _likely_src + " (partial)",
                })
                st.switch_page(
                    "ui/ent_accounts.py" if "Territory" in role else "ui/velocity_accounts.py"
                )
    spacer("md")

    run_disabled = (not vel_mode_a and df is None) or (vel_mode_a and not mode_a_ready) or not agents_to_run
    run_label = "EXECUTE RESEARCH PIPELINE"
    if partial_path and st.session_state.get(resume_choice_key) == "resume":
        run_label = "▶ RESUMING — START NOW"

    run_button = st.button(
        run_label,
        type="primary",
        use_container_width=True,
        disabled=run_disabled,
    )

    if run_button and agents_to_run and (df is not None or mode_a_ready):
        # Stable display labels per agent key
        agent_labels = {
            AGENT_TECH_STACK:  "Tech Stack",
            AGENT_HIRING:      "Hiring",
            AGENT_NEWS:        "News",
            AGENT_POSITION:    "Position",
            AGENT_REGULATORY:  "Regulatory",
            AGENT_PROFILE:     "Profile",
            AGENT_STAKEHOLDER: "Stakeholders",
            AGENT_PAIN_POINTS: "Pain Points",
            AGENT_ADVISOR:     "Advisor",
        }
        active_order = [k for k in agent_labels if k in agents_to_run]

        # ── Live-run chrome slots ────────────────────────────────────────
        live_header  = st.empty()
        progress_bar = st.progress(0)
        status_text  = st.empty()
        agent_grid   = st.empty()
        ticker_slot  = st.empty()
        stream_slot  = st.empty()

        # State accumulators across iterations
        agent_states: dict[str, str] = {k: "pending" for k in active_order}
        account_times: list[float] = []
        account_start_ref = {"t": time.time()}
        total_tokens = {"input": 0, "output": 0}

        def _render_agent_grid():
            pills = "  ".join(status_pill(agent_states[k], agent_labels[k]) for k in active_order)
            agent_grid.markdown(
                f"<div style='display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 4px 0'>{pills}</div>",
                unsafe_allow_html=True,
            )

        def _render_ticker():
            tin, tout = total_tokens["input"], total_tokens["output"]
            ticker_slot.markdown(
                f"<div style='color:{MUTED};font-size:{TYPE['caption']};margin-top:4px'>"
                f"Tokens used so far — "
                f"<strong style='color:{ACCENT}'>{tin:,}</strong> in · "
                f"<strong style='color:{ACCENT}'>{tout:,}</strong> out</div>",
                unsafe_allow_html=True,
            )

        def _format_eta(remaining: int) -> str:
            if not account_times or remaining <= 0:
                return "—"
            import statistics as _stats
            med = _stats.median(account_times)
            secs = int(med * remaining)
            if secs < 60:
                return f"~{secs}s"
            m, s = divmod(secs, 60)
            if m < 60:
                return f"~{m}m {s}s"
            h, m = divmod(m, 60)
            return f"~{h}h {m}m"

        # ── Mode A: discover accounts first ──────────────────────────────
        accounts: list[dict] = []
        src_name = ""

        if vel_mode_a:
            countries = [c.strip() for c in vel_countries_input.split(",") if c.strip()]
            industries = [i.strip() for i in vel_industries_input.split(",") if i.strip()]
            status_text.caption("Discovering candidate companies…")
            discovery_agent = CompanyDiscoveryAgent()
            accounts, disc_limitations = discovery_agent.run(
                countries=countries, industries=industries, count=int(vel_count),
            )
            if disc_limitations:
                for lim in disc_limitations:
                    st.caption(f"Discovery: {lim}")
            src_name = f"agent_curated_{'+'.join(countries)}_{'+'.join(industries)}"
        else:
            accounts = df.to_dict(orient="records")
            src_name = uploaded_file.name if uploaded_file else "velocity_list"

        # ── ENT dedup ─────────────────────────────────────────────────────
        ent_set: set[str] = st.session_state.get("ent_company_set", set())
        if ent_set:
            before = len(accounts)
            accounts = [
                acc for acc in accounts
                if acc.get("company", "").strip().lower() not in ent_set
                and acc.get("domain", "").strip().lower() not in ent_set
            ]
            removed = before - len(accounts)
            if removed:
                st.caption(f"{removed} ENT account(s) removed from Velocity list.")

        if not accounts:
            st.error("No accounts to analyze after filtering. Adjust your inputs and try again.")
            st.stop()

        # ── Resume gate ───────────────────────────────────────────────────
        resume_from: list = []
        if partial_path and st.session_state.get(resume_choice_key) == "resume":
            try:
                resume_from, _ = load_partial_run(partial_path)
            except Exception:
                resume_from = []
            if resume_from:
                st.caption(f"Resuming — {len(resume_from)} account(s) will be skipped.")

        total = len(accounts)
        live_header.markdown(
            f"<div style='color:{TEXT};font-size:{TYPE['h2']};font-weight:700;"
            f"margin-bottom:6px'>Running {total} account(s)</div>",
            unsafe_allow_html=True,
        )
        _render_agent_grid()
        _render_ticker()

        def update_progress(current, total_count, company):
            # Account-level callback. Reset per-agent grid; refresh ETA.
            nonlocal_done = current - 1
            elapsed = time.time() - account_start_ref["t"]
            if nonlocal_done >= 1:
                account_times.append(elapsed)
            account_start_ref["t"] = time.time()
            for k in active_order:
                agent_states[k] = "pending"
            remaining = total_count - current + 1
            eta = _format_eta(remaining)
            progress_bar.progress(min(1.0, (current - 1) / max(total_count, 1)))
            status_text.markdown(
                f"<span style='color:{TEXT};font-weight:600'>Account {current} of {total_count}</span>"
                f" &nbsp;·&nbsp; <span style='color:{ACCENT}'>{company}</span>"
                f" &nbsp;·&nbsp; <span style='color:{MUTED}'>ETA {eta}</span>",
                unsafe_allow_html=True,
            )
            _render_agent_grid()

        def on_agent_state(agent_key: str, state: str):
            if agent_key in agent_states:
                agent_states[agent_key] = state
                _render_agent_grid()

        director = DirectorAgent(role=role)
        handle = begin_run(role, src_name)

        def checkpoint(account_result, all_so_far):
            save_checkpoint(handle, all_so_far)
            # Update token ticker
            usage = account_result.get("token_usage", {}) or {}
            for v in usage.values():
                total_tokens["input"]  += int(v.get("input", 0) or 0)
                total_tokens["output"] += int(v.get("output", 0) or 0)
            _render_ticker()
            # Streaming results preview — top 5 by score so far
            top5 = sorted(all_so_far, key=lambda x: -x.get("total_score", 0))[:5]
            rows_html = ""
            for r in top5:
                comp = r.get("company", "")
                sc = round(r.get("total_score", 0), 1)
                rows_html += (
                    f"<div style='display:flex;justify-content:space-between;align-items:center;"
                    f"padding:8px 12px;border-bottom:1px solid {BORDER}'>"
                    f"<span style='color:{TEXT};font-weight:600;font-size:{TYPE['small']}'>{comp}</span>"
                    f"<span style='color:{ACCENT};font-weight:700'>{sc}</span></div>"
                )
            stream_slot.markdown(
                f"<div style='background:{CARD};border:1px solid {BORDER};"
                f"border-radius:{RADIUS['md']}px;margin-top:14px;overflow:hidden'>"
                f"<div style='padding:10px 12px;color:{MUTED};font-size:{TYPE['micro']};"
                f"text-transform:uppercase;letter-spacing:0.08em;font-weight:600;"
                f"border-bottom:1px solid {BORDER}'>Top results so far · "
                f"{len(all_so_far)} done</div>{rows_html}</div>",
                unsafe_allow_html=True,
            )

        try:
            results = director.run(
                accounts,
                progress_callback=update_progress,
                agents_to_run=agents_to_run,
                on_account_complete=checkpoint,
                resume_from=resume_from,
                agent_progress_callback=on_agent_state,
            )
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

        progress_bar.progress(1.0)
        status_text.markdown(
            f"<span style='color:{ACCENT};font-weight:700'>✓ Analysis complete</span> &nbsp;·&nbsp; "
            f"<span style='color:{MUTED}'>{len(results)} accounts ranked</span>",
            unsafe_allow_html=True,
        )

        saved_path = finalize_run(handle, results)

        tabs_key = "ent_tabs" if "Territory" in role else "vel_tabs"
        if tabs_key not in st.session_state:
            st.session_state[tabs_key] = []
        st.session_state[tabs_key].append({
            "type":  "run",
            "path":  saved_path,
            "label": src_name,
        })
        st.session_state.pop(resume_choice_key, None)

        if "Territory" in role:
            st.switch_page("ui/ent_accounts.py")
        else:
            st.switch_page("ui/velocity_accounts.py")
