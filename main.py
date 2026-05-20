import streamlit as st

st.set_page_config(
    page_title="Sonar AI Sales Agent",
    page_icon="assets/sonar_logo.png" if __import__("os").path.exists("assets/sonar_logo.png") else "🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = {
    "Sales Agent": [
        st.Page("ui/home.py", title="Home", icon="🏠"),
        st.Page("ui/ent_accounts.py", title="ENT Account Lists", icon="🏢"),
        st.Page("ui/velocity_accounts.py", title="Velocity Account Lists", icon="⚡"),
    ],
    "Configuration": [
        st.Page("ui/settings_page.py", title="Settings", icon="⚙️"),
        st.Page("ui/token_usage.py", title="Token Usage", icon="🔢"),
    ],
}

pg = st.navigation(pages)
pg.run()
