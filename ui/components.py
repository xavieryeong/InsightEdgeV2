"""
Component primitives — small, focused helpers for consistent UI markup.

Each function emits HTML through st.markdown or wraps a Streamlit container,
backed by ``ui.design`` tokens. Use these instead of inline ``style=""`` so
visual changes propagate via design.py.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Sequence

import streamlit as st

from ui.design import (
    ACCENT, ACCENT_80, ACCENT_SOFT, BORDER, BORDER_HI, CARD, CARD_HOVER,
    MUTED, RADIUS, SPACE, STATUS_COLORS, TEXT, TEXT_DIM, TYPE,
)


# ── Spacers / dividers ──────────────────────────────────────────────────────

def spacer(size: str = "md"):
    """Vertical whitespace using the SPACE scale."""
    px = SPACE.get(size, SPACE["md"])
    st.markdown(f"<div style='height:{px}px'></div>", unsafe_allow_html=True)


def divider(margin: str = "sm"):
    px = SPACE.get(margin, SPACE["sm"])
    st.markdown(
        f"<hr style='border:0;border-top:1px solid {BORDER};margin:{px}px 0'>",
        unsafe_allow_html=True,
    )


# ── Text primitives ─────────────────────────────────────────────────────────

def micro_label(text: str, color: str = MUTED):
    """Uppercase micro label used everywhere as section eyebrow."""
    st.markdown(
        f"<span style='color:{color};font-size:{TYPE['micro']};"
        f"text-transform:uppercase;letter-spacing:0.08em;font-weight:600'>"
        f"{text}</span>",
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str | None = None):
    st.markdown(
        f"<h3 style='color:{TEXT};font-size:{TYPE['h2']};margin:0 0 4px 0;"
        f"letter-spacing:-0.01em'>{title}</h3>",
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(
            f"<div style='color:{MUTED};font-size:{TYPE['caption']};"
            f"margin-bottom:{SPACE['sm']}px'>{subtitle}</div>",
            unsafe_allow_html=True,
        )


def kv_row(label: str, value: str, value_color: str = TEXT):
    st.markdown(
        f"<div style='margin-bottom:6px;line-height:1.6'>"
        f"<strong style='color:{ACCENT}'>{label}:</strong> "
        f"<span style='color:{value_color};font-size:{TYPE['small']}'>{value}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ── Pills / badges ──────────────────────────────────────────────────────────

def pill_html(text: str, color: str = ACCENT, variant: str = "soft") -> str:
    """Return the HTML for a pill — for embedding inside other markup."""
    if variant == "solid":
        return (
            f"<span style='background:{color};color:#0b1220;"
            f"padding:2px 10px;border-radius:{RADIUS['sm']}px;"
            f"font-size:{TYPE['micro']};font-weight:700;text-transform:uppercase;"
            f"letter-spacing:0.05em;display:inline-block'>{text}</span>"
        )
    return (
        f"<span style='background:{color}22;color:{color};"
        f"padding:2px 10px;border-radius:{RADIUS['sm']}px;"
        f"font-size:{TYPE['micro']};font-weight:700;text-transform:uppercase;"
        f"letter-spacing:0.05em;display:inline-block;white-space:nowrap'>{text}</span>"
    )


def pill(text: str, color: str = ACCENT, variant: str = "soft"):
    st.markdown(pill_html(text, color, variant), unsafe_allow_html=True)


def status_pill(state: str, label: str) -> str:
    """Return pill HTML for an agent execution state."""
    color = STATUS_COLORS.get(state, MUTED)
    icon = {"pending": "•", "running": "●", "done": "✓", "error": "✗"}.get(state, "•")
    pulse = ""
    if state == "running":
        pulse = (
            "animation:si-pulse 1.2s ease-in-out infinite;"
            "box-shadow:0 0 0 0 " + color + ";"
        )
    return (
        f"<span style='display:inline-flex;align-items:center;gap:6px;"
        f"background:{color}1a;color:{color};"
        f"padding:4px 10px;border-radius:{RADIUS['pill']}px;"
        f"font-size:{TYPE['micro']};font-weight:600;letter-spacing:0.04em;"
        f"border:1px solid {color}44;{pulse}'>"
        f"<span style='font-size:0.9em;line-height:1'>{icon}</span>"
        f"{label}</span>"
    )


# ── Cards ───────────────────────────────────────────────────────────────────

def metric_card(label: str, value: str, sublabel: str = "", accent: str = ACCENT,
                size: str = "lg"):
    value_size = "1.75rem" if size == "lg" else TYPE["h1"]
    sub_html = (
        f"<div style='color:{MUTED};font-size:{TYPE['caption']};margin-top:6px'>"
        f"{sublabel}</div>"
        if sublabel else ""
    )
    st.markdown(
        f"<div style='background:{CARD};border:1px solid {BORDER};"
        f"border-radius:{RADIUS['md']}px;padding:14px 18px;height:100%;"
        f"border-left:3px solid {accent}'>"
        f"<div style='color:{MUTED};font-size:{TYPE['micro']};"
        f"text-transform:uppercase;letter-spacing:0.08em;font-weight:600;"
        f"margin-bottom:6px'>{label}</div>"
        f"<div style='color:{TEXT};font-size:{value_size};font-weight:700;"
        f"line-height:1.1;letter-spacing:-0.02em'>{value}</div>"
        f"{sub_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def card_open(border_accent: str | None = None, padding: str = "md"):
    """Open a styled card div. Pair with card_close()."""
    border = f"border:1px solid {border_accent}" if border_accent else f"border:1px solid {BORDER}"
    pad = SPACE.get(padding, SPACE["md"])
    st.markdown(
        f"<div style='background:{CARD};{border};border-radius:{RADIUS['md']}px;"
        f"padding:{pad}px'>",
        unsafe_allow_html=True,
    )


def card_close():
    st.markdown("</div>", unsafe_allow_html=True)


# ── Score visualisation ────────────────────────────────────────────────────

def score_bar_html(breakdown: dict[str, float], total: float | None = None,
                   width_px: int = 220) -> str:
    """Horizontal stacked bar visualising per-signal score contributions.

    ``breakdown`` is ``{label: numeric_score}``; segments are coloured using
    ui.design.SIGNAL_COLORS where keys match, falling back to a rotation.
    """
    from ui.design import SIGNAL_COLORS

    items = [(k, max(0.0, float(v or 0))) for k, v in breakdown.items()]
    items = [(k, v) for k, v in items if v > 0]
    if not items:
        return (
            f"<span style='color:{MUTED};font-size:{TYPE['caption']}'>—</span>"
        )

    total_calc = sum(v for _, v in items)
    if total is None:
        total = total_calc

    palette = [
        SIGNAL_COLORS.get(k, ACCENT) for k, _ in items
    ]
    segs = ""
    for (k, v), c in zip(items, palette):
        pct = (v / total_calc) * 100 if total_calc else 0
        segs += (
            f"<span title='{k}: {v:.1f}' style='display:inline-block;"
            f"width:{pct:.2f}%;background:{c};height:100%'></span>"
        )

    return (
        f"<div style='display:inline-flex;align-items:center;gap:10px;"
        f"min-width:{width_px}px;max-width:100%'>"
        f"<div style='flex:1;height:8px;background:{BORDER};border-radius:"
        f"{RADIUS['pill']}px;overflow:hidden;display:flex'>{segs}</div>"
        f"<span style='font-weight:700;color:{TEXT};font-size:{TYPE['small']};"
        f"min-width:36px;text-align:right'>{total:.1f}</span>"
        f"</div>"
    )


def score_bar(breakdown: dict[str, float], total: float | None = None):
    st.markdown(score_bar_html(breakdown, total), unsafe_allow_html=True)


# ── Bulleted text from sentences ────────────────────────────────────────────

def bullets_html(text: str, color: str = MUTED, size: str = "small") -> str:
    """Split a paragraph on sentence boundaries and render as a bullet list."""
    import re as _re
    sentences = [s.strip() for s in _re.split(r'(?<=[.!?])\s+', (text or "").strip()) if s.strip()]
    if not sentences:
        return ""
    items = "".join(
        f"<li style='color:{color};font-size:{TYPE[size]};line-height:1.6;"
        f"margin-bottom:3px'>{s}</li>"
        for s in sentences
    )
    return f"<ul style='margin:4px 0 0 0;padding-left:18px'>{items}</ul>"


# ── Internal: animation keyframes (loaded once via theme) ──────────────────

_PULSE_KEYFRAMES = """
<style>
@keyframes si-pulse {
  0%   { box-shadow: 0 0 0 0 currentColor; opacity: 1; }
  70%  { box-shadow: 0 0 0 6px transparent; opacity: 0.85; }
  100% { box-shadow: 0 0 0 0 transparent; opacity: 1; }
}
</style>
"""


def inject_animations():
    """Inject keyframes used by status_pill etc. Call once per page after theme."""
    st.markdown(_PULSE_KEYFRAMES, unsafe_allow_html=True)
