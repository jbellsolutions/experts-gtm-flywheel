"""Brand tokens for the visual system (template defaults).

A neutral starting palette — deep navy + a sky->blue->violet gradient, Inter
headlines, white-on-navy. The onboarding assistant sets WORDMARK/HANDLE; recolor
the palette to your brand any time.
"""
from __future__ import annotations

# Canvas — LinkedIn portrait (best dwell time on mobile).
WIDTH = 1080
HEIGHT = 1350

# Palette
NAVY = "#0B1020"
NAVY_GLOW = "#7C3AED"        # purple, used as a faint radial glow on dark
GRAD_START = "#0EA5E9"       # sky
GRAD_MID = "#3457E0"         # blue
GRAD_END = "#8B5CF6"         # violet

WHITE = "#FFFFFF"
TEXT_LIGHT = "#E7EAF2"
TEXT_MUTED = "#9AA6C0"
TEXT_FAINT = "#7E879B"
BORDER = "#28365A"

# Type — bundled static Inter weights (see assets/brand/fonts, installed in
# Dockerfile.worker so fontconfig resolves font-weight to the right instance).
FONT = "Inter"
W_BLACK = 900
W_BOLD = 700
W_SEMI = 600
W_REG = 400

# Brand text
WORDMARK = "[YOUR BRAND]"
HANDLE = "[Your Name · Your Title]"
CTA_DEFAULT = "Follow for the playbook"
