import streamlit as st
from ui.theme import inject_theme
from ui.components import micro_label, spacer
from ui.design import (
    ACCENT, ACCENT_SOFT, BORDER, CARD, DANGER, INFO, MUTED,
    RADIUS, SUCCESS, TEXT, TEXT_DIM, TYPE, WARN,
)
from ui.results_store import list_runs
from ui.schedule_store import (
    create_schedule, delete_schedule, list_schedules, update_status,
)
from agents.director import (
    ROLE_TERRITORY_MANAGER, ROLE_VELOCITY,
    AGENT_TECH_STACK, AGENT_HIRING, AGENT_NEWS, AGENT_POSITION,
    AGENT_PROFILE, AGENT_REGULATORY, AGENT_STAKEHOLDER,
    AGENT_PAIN_POINTS, AGENT_ADVISOR,
)

inject_theme()

# ── Page header ──────────────────────────────────────────────────────────────

st.markdown(f"""
<div style="display:flex;align-items:center;gap:14px;margin-bottom:8px">
  <div style="background:{ACCENT};width:36px;height:36px;border-radius:9px;
              display:flex;align-items:center;justify-content:center;flex-shrink:0">
    <span style="color:#050a14;font-weight:900;font-size:1.1rem">⏱</span>
  </div>
  <div>
    <div style="color:{TEXT};font-size:1.35rem;font-weight:700;line-height:1.2">
      Scheduled Runs
    </div>
    <div style="color:{MUTED};font-size:0.8rem">
      Automate recurring research pipelines
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# Demo-mode banner
st.markdown(f"""
<div style="background:rgba(245,158,11,0.1);border:1px solid {WARN}55;
     border-radius:{RADIUS['md']}px;padding:10px 16px;margin-bottom:20px;
     display:flex;align-items:center;gap:10px">
  <span style="font-size:1rem">⚠️</span>
  <span style="color:{WARN};font-size:{TYPE['small']}">
    <strong>Demo mode:</strong> schedules are saved for display only and do not
    trigger automatic agent execution yet.
  </span>
</div>
""", unsafe_allow_html=True)

# ── Layout: form left, table right ───────────────────────────────────────────

col_form, col_table = st.columns([1, 1.6], gap="large")

# ── Helper: collect available account lists ──────────────────────────────────

def _get_account_lists() -> list[tuple[str, str]]:
    """Return [(display_label, source_filename), ...] from both roles."""
    items: list[tuple[str, str]] = []
    for role in [ROLE_TERRITORY_MANAGER, ROLE_VELOCITY]:
        for run in list_runs(role):
            label = f"{run['source_filename']}  ({role.split()[0]})"
            items.append((label, run["source_filename"]))
    # Deduplicate by source_filename
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for label, src in items:
        if src not in seen:
            seen.add(src)
            unique.append((label, src))
    return unique

# ── CREATE SCHEDULE FORM ─────────────────────────────────────────────────────

with col_form:
    st.subheader("Create Schedule")

    account_lists = _get_account_lists()

    if not account_lists:
        st.info("No completed research batches found. Run an analysis first to create a schedule.")
    else:
        display_labels = [lbl for lbl, _ in account_lists]
        src_map = {lbl: src for lbl, src in account_lists}

        sched_name = st.text_input(
            "SCHEDULE NAME",
            placeholder="e.g. Weekly PH Banking Check",
            key="sched_name",
        )

        role_choice = st.radio(
            "WORKSTREAM",
            options=[ROLE_VELOCITY, ROLE_TERRITORY_MANAGER],
            horizontal=True,
            key="sched_role",
        )

        chosen_label = st.selectbox(
            "ACCOUNT LIST",
            options=display_labels,
            key="sched_list",
        )

        st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)
        micro_label("Agents to run")

        is_ent = role_choice == ROLE_TERRITORY_MANAGER

        ag_col1, ag_col2 = st.columns(2)
        with ag_col1:
            cb_tech    = st.checkbox("Tech Stack",      value=True,  key="sc_tech")
            cb_hiring  = st.checkbox("Hiring Signals",  value=True,  key="sc_hiring")
            cb_news    = st.checkbox("Public News",     value=True,  key="sc_news")
            cb_profile = st.checkbox("Company Profile", value=True,  key="sc_profile")
        with ag_col2:
            cb_position = st.checkbox("Company Position", value=True, key="sc_position")
            cb_advisor  = st.checkbox("Outreach Suggest", value=True, key="sc_advisor")
            if is_ent:
                cb_reg   = st.checkbox("Regulatory Impact",        value=True, key="sc_reg")
                cb_stake = st.checkbox("Stakeholder Intelligence", value=False, key="sc_stake")
                cb_pain  = False
            else:
                cb_pain  = st.checkbox("Developer Pain Points", value=True, key="sc_pain")
                cb_reg   = False
                cb_stake = False

        spacer("sm")

        freq = st.selectbox(
            "FREQUENCY",
            options=["Daily", "Weekly", "Monthly", "One-off"],
            key="sched_freq",
        )

        run_time = st.time_input(
            "PREFERRED RUN TIME",
            value=__import__("datetime").time(9, 0),
            key="sched_time",
        )

        lookback = st.select_slider(
            "SIGNAL LOOKBACK WINDOW (days)",
            options=[7, 14, 30, 90],
            value=30,
            key="sched_lookback",
        )

        spacer("md")

        can_create = bool(sched_name.strip())
        if not can_create:
            st.caption("Enter a schedule name to continue.")

        if st.button(
            "CREATE SCHEDULE",
            type="primary",
            use_container_width=True,
            disabled=not can_create,
        ):
            agents_selected: list[str] = []
            if cb_tech:     agents_selected.append(AGENT_TECH_STACK)
            if cb_hiring:   agents_selected.append(AGENT_HIRING)
            if cb_news:     agents_selected.append(AGENT_NEWS)
            if cb_profile:  agents_selected.append(AGENT_PROFILE)
            if cb_position: agents_selected.append(AGENT_POSITION)
            if cb_reg:      agents_selected.append(AGENT_REGULATORY)
            if cb_stake:    agents_selected.append(AGENT_STAKEHOLDER)
            if cb_pain:     agents_selected.append(AGENT_PAIN_POINTS)
            if cb_advisor:  agents_selected.append(AGENT_ADVISOR)

            if not agents_selected:
                st.warning("Select at least one agent.")
            else:
                create_schedule(
                    name=sched_name.strip(),
                    account_list=src_map[chosen_label],
                    role=role_choice,
                    agents=agents_selected,
                    frequency=freq,
                    preferred_time=run_time.strftime("%H:%M"),
                    lookback_days=lookback,
                )
                st.success(f'Schedule "{sched_name.strip()}" created.')
                st.rerun()

# ── SCHEDULE TABLE ────────────────────────────────────────────────────────────

_AGENT_LABELS = {
    AGENT_TECH_STACK:  "Tech Stack",
    AGENT_HIRING:      "Hiring",
    AGENT_NEWS:        "News",
    AGENT_POSITION:    "Position",
    AGENT_PROFILE:     "Profile",
    AGENT_REGULATORY:  "Regulatory",
    AGENT_STAKEHOLDER: "Stakeholders",
    AGENT_PAIN_POINTS: "Pain Points",
    AGENT_ADVISOR:     "Advisor",
}

_STATUS_COLOR = {
    "Active": SUCCESS,
    "Paused": WARN,
}

_FREQ_ICON = {
    "Daily":   "🔁",
    "Weekly":  "📅",
    "Monthly": "🗓️",
    "One-off": "⚡",
}

with col_table:
    st.subheader("Active Schedules")

    schedules = list_schedules()

    if not schedules:
        st.markdown(f"""
        <div style="background:{CARD};border:1px solid {BORDER};border-radius:{RADIUS['md']}px;
             padding:40px;text-align:center;color:{MUTED};font-size:{TYPE['small']}">
          No schedules yet. Create one using the form.
        </div>
        """, unsafe_allow_html=True)
    else:
        for sched in schedules:
            status_color = _STATUS_COLOR.get(sched["status"], MUTED)
            agent_pills = "  ".join(
                f"<span style='background:{ACCENT}18;color:{ACCENT};padding:2px 7px;"
                f"border-radius:999px;font-size:{TYPE['micro']};font-weight:600;"
                f"border:1px solid {ACCENT}33'>{_AGENT_LABELS.get(a, a)}</span>"
                for a in sched.get("agents", [])
            )
            freq_icon = _FREQ_ICON.get(sched["frequency"], "⏱")

            st.markdown(f"""
            <div style="background:{CARD};border:1px solid {BORDER};
                 border-radius:{RADIUS['md']}px;padding:16px 18px;margin-bottom:12px">

              <div style="display:flex;justify-content:space-between;
                          align-items:flex-start;margin-bottom:10px">
                <div>
                  <span style="color:{TEXT};font-size:{TYPE['h3']};font-weight:700">
                    {sched['name']}
                  </span>
                  &nbsp;
                  <span style="background:{status_color}22;color:{status_color};
                        padding:2px 9px;border-radius:999px;font-size:{TYPE['micro']};
                        font-weight:700;border:1px solid {status_color}44">
                    {sched['status']}
                  </span>
                </div>
                <span style="color:{MUTED};font-size:{TYPE['caption']}">
                  Created {sched['created_at']}
                </span>
              </div>

              <div style="display:grid;grid-template-columns:1fr 1fr;
                          gap:6px 20px;margin-bottom:10px">
                <div>
                  <span style="color:{MUTED};font-size:{TYPE['micro']};
                        text-transform:uppercase;letter-spacing:0.06em">Account List</span><br>
                  <span style="color:{TEXT_DIM};font-size:{TYPE['small']}">
                    {sched['account_list']}
                  </span>
                </div>
                <div>
                  <span style="color:{MUTED};font-size:{TYPE['micro']};
                        text-transform:uppercase;letter-spacing:0.06em">Frequency</span><br>
                  <span style="color:{TEXT_DIM};font-size:{TYPE['small']}">
                    {freq_icon} {sched['frequency']} at {sched['preferred_time']}
                  </span>
                </div>
                <div>
                  <span style="color:{MUTED};font-size:{TYPE['micro']};
                        text-transform:uppercase;letter-spacing:0.06em">Lookback Window</span><br>
                  <span style="color:{TEXT_DIM};font-size:{TYPE['small']}">
                    {sched['lookback_days']} days
                  </span>
                </div>
                <div>
                  <span style="color:{MUTED};font-size:{TYPE['micro']};
                        text-transform:uppercase;letter-spacing:0.06em">Next Run</span><br>
                  <span style="color:{ACCENT};font-size:{TYPE['small']};font-weight:600">
                    {sched['next_run']}
                  </span>
                </div>
                <div>
                  <span style="color:{MUTED};font-size:{TYPE['micro']};
                        text-transform:uppercase;letter-spacing:0.06em">Last Run</span><br>
                  <span style="color:{MUTED};font-size:{TYPE['small']};font-style:italic">
                    {sched['last_run']}
                  </span>
                </div>
                <div>
                  <span style="color:{MUTED};font-size:{TYPE['micro']};
                        text-transform:uppercase;letter-spacing:0.06em">Workstream</span><br>
                  <span style="color:{TEXT_DIM};font-size:{TYPE['small']}">
                    {sched['role'].split('(')[0].strip()}
                  </span>
                </div>
              </div>

              <div style="margin-bottom:8px">
                <span style="color:{MUTED};font-size:{TYPE['micro']};
                      text-transform:uppercase;letter-spacing:0.06em">Agents</span><br>
                <div style="margin-top:4px">{agent_pills}</div>
              </div>

            </div>
            """, unsafe_allow_html=True)

            # Action buttons
            btn1, btn2, btn3 = st.columns([1, 1, 1])
            sid = sched["id"]

            with btn1:
                if sched["status"] == "Active":
                    if st.button("⏸ Pause", key=f"pause_{sid}", use_container_width=True):
                        update_status(sid, "Paused")
                        st.rerun()
                else:
                    if st.button("▶ Resume", key=f"resume_{sid}", use_container_width=True, type="primary"):
                        update_status(sid, "Active")
                        st.rerun()

            with btn2:
                st.button("▷ Run Now", key=f"run_{sid}", use_container_width=True, disabled=True,
                          help="Demo mode — manual runs must be triggered from the Home page.")

            with btn3:
                if st.button("🗑 Delete", key=f"del_{sid}", use_container_width=True):
                    delete_schedule(sid)
                    st.rerun()

            st.markdown("<div style='margin-bottom:4px'></div>", unsafe_allow_html=True)
