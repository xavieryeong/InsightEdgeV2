import streamlit as st
import streamlit.components.v1 as components
from ui.results_store import list_runs, load_run, delete_run
from ui.account_render import render_run_content, render_account_content, add_tab, prefetch_advisor
from ui.theme import inject_theme
from agents.director import ROLE_TERRITORY_MANAGER

inject_theme()

TABS_KEY = "ent_tabs"

if TABS_KEY not in st.session_state:
    st.session_state[TABS_KEY] = []

for _tc in st.session_state[TABS_KEY]:
    if _tc["type"] == "account":
        _d = load_run(_tc["run_path"])
        prefetch_advisor(_d["results"][_tc["idx"]])

tab_labels = ["📋 DASHBOARD"] + [t["label"].upper() for t in st.session_state[TABS_KEY]]
tabs = st.tabs(tab_labels)

nav_to = st.session_state.pop(TABS_KEY + "_navigate_to", None)
if nav_to is not None:
    components.html(
        f"<script>setTimeout(function(){{"
        f"var t=window.parent.document.querySelectorAll('[data-baseweb=\"tab\"]');"
        f"if(t&&t[{nav_to}])t[{nav_to}].click();"
        f"}},80);</script>",
        height=0,
    )

with tabs[0]:
    st.title("Enterprise Intelligence")
    st.markdown("Select a research batch to view account propensities.")
    st.markdown("---")

    runs = list_runs(ROLE_TERRITORY_MANAGER)
    if not runs:
        st.info("No research batches found. Run an analysis from the Home page to get started.")
    else:
        for run in runs:
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([3, 2, 1.2, 1.2, 0.6])
                c1.markdown(f"**{run['source_filename']}**")
                c2.caption(run["display_date"])
                c3.caption(f"{run['company_count']} companies")
                if c4.button("VIEW BATCH", key=f"open_{run['path']}", use_container_width=True):
                    add_tab(TABS_KEY, {"type": "run", "path": run["path"], "label": run["source_filename"]})
                    st.rerun()
                if c5.button("✕", key=f"del_{run['path']}", help="Delete this run"):
                    delete_run(run["path"])
                    st.session_state[TABS_KEY] = [
                        t for t in st.session_state[TABS_KEY]
                        if t.get("path") != run["path"] and t.get("run_path") != run["path"]
                    ]
                    st.rerun()
                st.markdown("<hr style='border:0;border-top:1px solid #1e293b;margin:4px 0'>", unsafe_allow_html=True)

for i, tab_config in enumerate(st.session_state[TABS_KEY]):
    with tabs[i + 1]:
        col_hd, col_close = st.columns([6, 1])
        with col_close:
            if st.button("CLOSE", key=f"close_{TABS_KEY}_{i}", use_container_width=True):
                st.session_state[TABS_KEY].pop(i)
                st.rerun()

        if tab_config["type"] == "run":
            data = load_run(tab_config["path"])
            col_hd.subheader(tab_config["label"])
            col_hd.caption(
                f"{data['metadata'].get('date', '')[:16].replace('T', ' ')}  ·  {data['metadata']['company_count']} companies"
            )
            st.markdown("---")
            render_run_content(data["results"], tab_config["path"], TABS_KEY)

        elif tab_config["type"] == "account":
            data = load_run(tab_config["run_path"])
            r = data["results"][tab_config["idx"]]
            col_hd.subheader(r["company"])
            st.markdown("---")
            render_account_content(r, show_email=True, run_path=tab_config["run_path"])
