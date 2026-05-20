"""
Global theme — InsightEdge dark navy palette.

Single source of truth: ui.design tokens.
Call inject_theme() at the top of every page.
"""
from __future__ import annotations

import streamlit as st

from ui.design import (
    ACCENT, ACCENT_80, ACCENT_GLOW, ACCENT_SOFT, BG, BG_ELEVATED, BORDER,
    BORDER_HI, CARD, CARD_HOVER, FONT_FAMILY, INPUT_BG, INPUT_TEXT, MUTED,
    RADIUS, SHADOW_GLOW, SPACE, TEXT, TEXT_DIM, TYPE,
)
from ui.components import inject_animations


# Re-exports kept for any legacy import sites (theme.ACCENT, etc.)
__all__ = ["inject_theme", "ACCENT", "ACCENT_80", "BG", "CARD", "BORDER", "TEXT", "MUTED"]


def _css() -> str:
    return f"""
<style>
/* ── Inter font ─────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Tokens as CSS variables (so dynamic markup can read them) ─ */
:root {{
    --si-bg: {BG};
    --si-card: {CARD};
    --si-border: {BORDER};
    --si-accent: {ACCENT};
    --si-text: {TEXT};
    --si-muted: {MUTED};
}}

/* ── Page background — subtle radial gradient for depth ────── */
.stApp {{
    background:
        radial-gradient(1200px 600px at 0% 0%, {BG_ELEVATED} 0%, {BG} 60%) no-repeat,
        {BG};
    background-attachment: fixed;
    font-family: {FONT_FAMILY} !important;
}}
[data-testid="stHeader"] {{
    background-color: rgba(5, 10, 20, 0.6) !important;
    backdrop-filter: blur(10px);
}}

html, body, [class*="css"] {{
    font-family: {FONT_FAMILY} !important;
}}

/* ── Sidebar ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background-color: {CARD} !important;
    border-right: 1px solid {BORDER};
}}

/* ── Typography ─────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6 {{
    color: {TEXT} !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
    font-family: {FONT_FAMILY} !important;
}}
p, span, label, li {{
    color: {MUTED};
}}
.stMarkdown p {{
    color: {MUTED};
    line-height: 1.65;
    font-size: {TYPE['body']};
}}
b, strong, .stMarkdown strong {{
    color: {ACCENT} !important;
    font-weight: 700;
}}

/* ── Block container top padding ────────────────────────────── */
.block-container {{
    padding-top: 3.5rem !important;
    max-width: 1400px;
}}

/* ── Input Fields (White Surface) ───────────────────────────── */
.stTextInput input, .stTextArea textarea, .stNumberInput input,
.stSelectbox [data-baseweb="select"] {{
    background-color: {INPUT_BG} !important;
    color: {INPUT_TEXT} !important;
    border-radius: {RADIUS['sm']}px !important;
    border: 1px solid {BORDER} !important;
    padding: 12px !important;
    font-family: {FONT_FAMILY} !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {{
    border-color: {ACCENT} !important;
    box-shadow: 0 0 0 2px {ACCENT_GLOW} !important;
}}

/* ── Widget labels ───────────────────────────────────────────── */
[data-testid="stWidgetLabel"] p {{
    color: {TEXT} !important;
    font-size: {TYPE['micro']} !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    font-weight: 600 !important;
    margin-bottom: 8px !important;
}}
.stCaption, .stCaption > p, small {{
    color: {MUTED} !important;
}}

/* ── Buttons ─────────────────────────────────────────────────── */
div.stButton > button, div.stDownloadButton > button {{
    border-radius: {RADIUS['sm']}px !important;
    padding: 10px 22px !important;
    font-weight: 600 !important;
    transition: all 0.15s ease;
    font-family: {FONT_FAMILY} !important;
}}
div.stButton > button[kind="primary"], div.stDownloadButton > button[kind="primary"] {{
    background-color: {ACCENT} !important;
    color: #ffffff !important;
    border: none !important;
    font-weight: 700 !important;
}}
div.stButton > button[kind="primary"] p,
div.stButton > button[kind="primary"] span {{
    color: #ffffff !important;
    font-weight: 700 !important;
}}
div.stButton > button[kind="primary"]:hover {{
    background-color: {ACCENT_80} !important;
    transform: translateY(-1px);
    box-shadow: {SHADOW_GLOW};
}}
div.stButton > button[kind="secondary"] {{
    background-color: transparent !important;
    color: {ACCENT} !important;
    border: 1px solid {ACCENT} !important;
}}
div.stButton > button[kind="secondary"]:hover {{
    background-color: {ACCENT_SOFT} !important;
}}
div.stButton > button[kind="tertiary"] {{
    background: none !important;
    border: none !important;
    padding: 0 !important;
    color: {ACCENT} !important;
    font-weight: 600 !important;
    text-decoration: underline;
    cursor: pointer;
    min-height: unset !important;
}}
div.stButton > button[kind="tertiary"]:hover {{
    color: {ACCENT_80} !important;
}}

/* ── Cards & Expanders ───────────────────────────────────────── */
.streamlit-expanderHeader, [data-testid="stExpander"] summary {{
    background-color: {CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: {RADIUS['md']}px !important;
    padding: 12px 16px !important;
    color: {TEXT} !important;
    font-weight: 600 !important;
}}
.streamlit-expanderHeader:hover, [data-testid="stExpander"] summary:hover {{
    background-color: {CARD_HOVER} !important;
    border-color: {BORDER_HI} !important;
}}
.streamlit-expanderHeader[aria-expanded="true"], details[open] > summary {{
    border-radius: {RADIUS['md']}px {RADIUS['md']}px 0 0 !important;
    border-bottom-color: {ACCENT} !important;
}}
.streamlit-expanderContent {{
    background-color: {CARD} !important;
    border: 1px solid {BORDER} !important;
    border-top: none !important;
    border-radius: 0 0 {RADIUS['md']}px {RADIUS['md']}px !important;
    padding: 1rem !important;
}}

/* ── Tabs ────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 24px;
    background-color: transparent;
    border-bottom: 1px solid {BORDER} !important;
}}
.stTabs [data-baseweb="tab-highlight"] {{
    background-color: transparent !important;
}}
.stTabs [data-baseweb="tab-border"] {{
    background-color: transparent !important;
    display: none !important;
}}
.stTabs [data-baseweb="tab"] {{
    color: {MUTED} !important;
    font-weight: 500 !important;
    padding: 10px 4px !important;
    font-size: {TYPE['small']} !important;
    font-family: {FONT_FAMILY} !important;
}}
.stTabs [aria-selected="true"] {{
    color: {ACCENT} !important;
    border-bottom: 2px solid {ACCENT} !important;
}}
.stTabs [data-baseweb="tab-panel"] {{
    padding-top: 1rem;
}}

/* ── Radio / Checkbox ────────────────────────────────────────── */
.stRadio > label, .stCheckbox > label {{ color: {TEXT} !important; }}

/* ── Progress bar ────────────────────────────────────────────── */
.stProgress > div > div > div > div {{
    background: linear-gradient(90deg, {ACCENT_80} 0%, {ACCENT} 100%) !important;
}}

/* ── Alerts ──────────────────────────────────────────────────── */
.stAlert {{ border-radius: {RADIUS['sm']}px !important; }}
.stInfo  {{ background-color: #0d1f38 !important; border-left-color: {ACCENT} !important; }}

/* ── File Uploader ───────────────────────────────────────────── */
[data-testid="stFileUploader"] section {{
    background-color: #2d3748 !important;
    border: 1px solid {BORDER} !important;
    border-radius: {RADIUS['sm']}px !important;
}}
[data-testid="stFileUploader"] section button {{
    background-color: #4a5568 !important;
    color: #ffffff !important;
    border: 1px solid #718096 !important;
    border-radius: {RADIUS['sm']}px !important;
}}
[data-testid="stFileUploader"] section small,
[data-testid="stFileUploader"] section span,
[data-testid="stFileUploader"] section p {{
    color: #e2e8f0 !important;
}}

/* ── Dividers ────────────────────────────────────────────────── */
hr {{ border-color: {BORDER} !important; margin: 0.75rem 0 !important; }}

/* ── Spinner ─────────────────────────────────────────────────── */
.stSpinner > div {{ border-top-color: {ACCENT} !important; }}

/* ── Selection ───────────────────────────────────────────────── */
::selection {{ background: {ACCENT_GLOW}; color: {TEXT}; }}

/* ── Scrollbar (webkit) ──────────────────────────────────────── */
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: {BG}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 5px; }}
::-webkit-scrollbar-thumb:hover {{ background: {BORDER_HI}; }}

/* ── Shared utility classes used by signal cards ─────────────── */
.si-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0 6px;
    font-size: {TYPE['small']};
}}
.si-table th {{
    text-align: left; padding: 10px 12px; color: {MUTED};
    font-size: {TYPE['micro']}; text-transform: uppercase; letter-spacing: 0.1em;
    border-bottom: 1px solid {BORDER};
}}
.si-table td {{
    padding: 14px 12px;
    background: {CARD};
    color: {TEXT};
    vertical-align: middle;
    border-top: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    word-break: break-word;
    white-space: normal;
    line-height: 1.5;
}}
.si-table td:first-child {{ border-left: 1px solid {BORDER}; border-radius: 8px 0 0 8px; }}
.si-table td:last-child  {{ border-right: 1px solid {BORDER}; border-radius: 0 8px 8px 0; }}
.si-table tr:hover td {{ background: {CARD_HOVER}; }}
.si-link {{
    color: {ACCENT}; text-decoration: none; font-weight: 600;
    display: inline-flex; align-items: center; gap: 4px;
}}
.si-link:hover {{ color: {ACCENT_80}; text-decoration: underline; }}
.si-badge {{
    display: inline-block;
    background: {ACCENT_SOFT}; color: {ACCENT};
    padding: 3px 10px; border-radius: {RADIUS['sm']}px;
    font-size: {TYPE['micro']}; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.05em;
}}
.si-news-card {{
    background: {CARD}; border: 1px solid {BORDER};
    border-radius: {RADIUS['lg']}px; padding: 18px 20px; margin-bottom: 10px;
    transition: border-color 0.2s ease, transform 0.15s ease;
}}
.si-news-card:hover {{ border-color: {ACCENT}; transform: translateY(-1px); }}
.si-row-card {{
    background: {CARD}; border: 1px solid {BORDER};
    border-radius: {RADIUS['sm']}px; padding: 12px 14px; margin-bottom: 6px;
    transition: border-color 0.15s ease;
}}
.si-row-card:hover {{ border-color: {BORDER_HI}; }}

/* ── Sticky rail used in account detail ─────────────────────── */
.si-sticky-rail {{
    position: sticky;
    top: 80px;
}}

/* ── Token ticker (top-right during runs) ───────────────────── */
.si-token-ticker {{
    position: fixed;
    top: 70px;
    right: 24px;
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: {RADIUS['md']}px;
    padding: 10px 14px;
    font-size: {TYPE['caption']};
    color: {TEXT};
    z-index: 100;
    box-shadow: 0 4px 12px rgba(0,0,0,0.35);
}}
</style>
"""


def inject_theme():
    st.markdown(_css(), unsafe_allow_html=True)
    inject_animations()
