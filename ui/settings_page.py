import streamlit as st
from config.settings import save_api_keys, MIN_NEWS_COUNT
import os
from dotenv import dotenv_values
from ui.theme import inject_theme

inject_theme()

st.title("Settings")
st.markdown("Enter your API keys below. Keys are saved to your local `.env` file.")
st.markdown("---")

env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
current = dotenv_values(env_path) if os.path.exists(env_path) else {}


def masked(val):
    if not val:
        return ""
    return val[:6] + "*" * (len(val) - 6) if len(val) > 6 else "***"


st.subheader("AI Model")
anthropic_key = st.text_input(
    "Anthropic API Key",
    placeholder="sk-ant-...",
    help="Get your key from console.anthropic.com",
    value="" if not current.get("ANTHROPIC_API_KEY") else "",
)
if current.get("ANTHROPIC_API_KEY"):
    st.caption(f"Current: {masked(current.get('ANTHROPIC_API_KEY'))}")

st.markdown("---")
st.subheader("Data Sources")
st.caption("Add keys for the data sources you have access to. Leave blank to skip.")

linkedin_key = st.text_input("LinkedIn API Key", placeholder="Optional")
github_token = st.text_input("GitHub Token", placeholder="Optional")
zoominfo_key = st.text_input("ZoomInfo API Key", placeholder="Optional")

st.markdown("---")
st.subheader("Analysis Settings")
st.caption("Control how agent outputs are displayed.")

min_news = st.number_input(
    "Minimum news articles to show per account",
    min_value=1,
    max_value=20,
    value=int(current.get("MIN_NEWS_COUNT", MIN_NEWS_COUNT)),
    step=1,
    help="The news panel will always show at least this many articles. If fewer scored articles exist, lower-confidence ones are included to fill the count.",
)

st.markdown("---")

if st.button("Save Settings", type="primary"):
    keys = {
        "ANTHROPIC_API_KEY": anthropic_key,
        "LINKEDIN_API_KEY": linkedin_key,
        "GITHUB_TOKEN": github_token,
        "ZOOMINFO_API_KEY": zoominfo_key,
    }
    keys = {k: v for k, v in keys.items() if v.strip()}
    keys["MIN_NEWS_COUNT"] = str(min_news)
    save_api_keys(keys)
    st.success("Settings saved. Restart the app for changes to take effect.")
