"""
Design tokens — single source of truth for colours, typography, spacing, radii.
Imported by ui/theme.py, ui/components.py, ui/account_render.py, ui/home.py.

Update tokens here and the rest of the UI follows. Avoid hard-coding hex codes
or pixel values in feature files.
"""
from __future__ import annotations

# ── Colour palette ──────────────────────────────────────────────────────────
BG          = "#050a14"
BG_ELEVATED = "#0a1322"     # subtle lift for hero / sticky chrome
CARD        = "#111827"
CARD_HOVER  = "#1a2638"
BORDER      = "#1e293b"
BORDER_HI   = "#2a3a52"
ACCENT      = "#00d4aa"
ACCENT_80   = "#00b894"
ACCENT_SOFT = "rgba(0,212,170,0.12)"
ACCENT_GLOW = "rgba(0,212,170,0.25)"
TEXT        = "#f8fafc"
TEXT_DIM    = "#cbd5e1"
MUTED       = "#94a3b8"
INPUT_BG    = "#ffffff"
INPUT_TEXT  = "#0f172a"

# Semantic roles
SUCCESS = "#22c55e"
WARN    = "#f59e0b"
DANGER  = "#ef4444"
INFO    = "#3b82f6"

# Company-position colour mapping (single source — was duplicated in
# account_render._POS_COLORS and render_account_content._pos_colors).
POSITION_COLORS = {
    "AI Leader":     ACCENT,
    "Early Adopter": INFO,
    "Mainstream":    WARN,
    "Skeptic":       "#f97316",
    "Laggard":       DANGER,
}

# Per-signal accent (used by score_bar and signal-type pills in advisor)
SIGNAL_COLORS = {
    "tech_stack":   "#8b5cf6",
    "hiring":       ACCENT,
    "hiring_patterns": ACCENT,
    "news":         INFO,
    "public_news":  INFO,
    "regulatory":   WARN,
    "regulatory_impact": WARN,
    "pain_points":  DANGER,
    "company_position": "#f97316",
    "company_profile":  MUTED,
    "stakeholder_intelligence": "#ec4899",
    "signal_advisor": ACCENT,
}

# DISC-style personality colours (4-colour model)
PERSONALITY_COLORS = {
    "Red":     DANGER,
    "Blue":    INFO,
    "Green":   SUCCESS,
    "Yellow":  "#eab308",
    "Unknown": MUTED,
}

# Live-run status pill colour mapping
STATUS_COLORS = {
    "pending": MUTED,
    "running": ACCENT,
    "done":    SUCCESS,
    "error":   DANGER,
}

# ── Typography ──────────────────────────────────────────────────────────────
FONT_FAMILY = (
    "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', "
    "Roboto, Oxygen, Ubuntu, sans-serif"
)
FONT_MONO = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

TYPE = {
    "display": "2rem",      # hero numbers, propensity score
    "h1":      "1.5rem",    # account name
    "h2":      "1.125rem",  # section header
    "h3":      "1rem",
    "body":    "0.9375rem", # 15px — main reading text
    "small":   "0.85rem",
    "caption": "0.78rem",
    "micro":   "0.7rem",    # uppercase labels
}

# ── Spacing (pixels) ────────────────────────────────────────────────────────
SPACE = {
    "xs": 4,
    "sm": 8,
    "md": 16,
    "lg": 24,
    "xl": 40,
    "2xl": 64,
}

# ── Radii ───────────────────────────────────────────────────────────────────
RADIUS = {
    "sm": 6,
    "md": 10,
    "lg": 14,
    "pill": 999,
}

# ── Shadow ──────────────────────────────────────────────────────────────────
SHADOW_SOFT = "0 2px 8px rgba(0,0,0,0.25)"
SHADOW_GLOW = f"0 4px 16px {ACCENT_GLOW}"
