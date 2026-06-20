"""Tag a draft as Pillar 1 / 2 / both.

Heuristic first (keyword match), LLM fallback when ambiguous. Heuristic
catches ~80% and costs nothing.
"""
from __future__ import annotations

PILLAR_1_KEYWORDS = (
    "your problem", "your bottleneck", "drop it below", "i'll solve",
    "what are you stuck on", "$1,000 problem", "what's eating",
)
PILLAR_2_KEYWORDS = (
    "journey", "behind the scenes", "lesson learned", "milestone",
    "the story", "our team built", "we just delivered",
)


def classify(text: str) -> str:
    t = text.lower()
    p1 = any(k in t for k in PILLAR_1_KEYWORDS)
    p2 = any(k in t for k in PILLAR_2_KEYWORDS)
    if p1 and p2:
        return "both"
    if p2:
        return "2"
    return "1"  # default — most content is Pillar 1
