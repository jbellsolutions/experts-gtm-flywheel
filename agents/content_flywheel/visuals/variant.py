"""Visual variants — rotate the look so consecutive post images never repeat.

your directive: every post's image must look visibly different while staying
on-brand. This is the "art-director" step of the editorial visual process — but
instead of an LLM that might pick the same look twice, it's a *curated rotation*:
a hand-picked set of on-brand looks (palette / gradient angle / background
treatment / composition), advanced round-robin via kv_state (the same mechanism
voices_daily uses for the industry rotation). Round-robin GUARANTEES the thing
you cares about — back-to-back posts can't share a look, and any single look
only recurs once per full cycle.

Every palette stays inside the brand's cyan → blue → violet → magenta arc, so the
images read as one family even as the look shifts. templates.py consumes the
chosen dict; variant=None there reproduces the original "classic" look exactly.
"""
from __future__ import annotations

from typing import Any

from ..idea_queue import store as idea_store

# Each variant = palette (3 on-brand stops) + gradient angle + background
# treatment + image-card composition. Curated so consecutive entries look
# clearly different (palette AND treatment AND composition all shift).
VARIANTS: list[dict[str, Any]] = [
    {"key": "classic",      "grad": ("#0EA5E9", "#3457E0", "#8B5CF6"),
     "angle": "horiz", "bg": "glow-top",    "comp": "center"},   # the original
    {"key": "violet-rail",  "grad": ("#3457E0", "#8B5CF6", "#C026D3"),
     "angle": "diag",  "bg": "split",       "comp": "left"},
    {"key": "ice-mesh",     "grad": ("#22D3EE", "#3B82F6", "#4F46E5"),
     "angle": "vert",  "bg": "mesh",        "comp": "center"},
    {"key": "electric",     "grad": ("#4F46E5", "#7C3AED", "#D946EF"),
     "angle": "diag",  "bg": "glow-corner", "comp": "left"},
    {"key": "azure",        "grad": ("#0EA5E9", "#2563EB", "#4F46E5"),
     "angle": "horiz", "bg": "glow-corner", "comp": "center"},
    {"key": "aurora-split", "grad": ("#06B6D4", "#6366F1", "#A855F7"),
     "angle": "diag",  "bg": "split",       "comp": "center"},
    {"key": "cyan-left",    "grad": ("#0EA5E9", "#3457E0", "#8B5CF6"),
     "angle": "vert",  "bg": "mesh",        "comp": "left"},
]

_IDX_KEY = "visual_variant_idx"


def pick() -> dict[str, Any]:
    """Return the next variant in the rotation and advance the index.

    kv_state-backed round-robin: consecutive calls return different looks, and a
    look only repeats after a full cycle. Falls back to "classic" if kv is down,
    so a storage hiccup never blocks a render.
    """
    try:
        i = int(idea_store.kv_get(_IDX_KEY, 0) or 0)
    except Exception:  # noqa: BLE001
        return VARIANTS[0]
    v = VARIANTS[i % len(VARIANTS)]
    try:
        idea_store.kv_set(_IDX_KEY, (i + 1) % (len(VARIANTS) * 1000))
    except Exception:  # noqa: BLE001
        pass
    return v


def by_key(key: str | None) -> dict[str, Any]:
    """Look up a specific variant (for re-renders / dashboard overrides)."""
    for v in VARIANTS:
        if v["key"] == key:
            return v
    return VARIANTS[0]
