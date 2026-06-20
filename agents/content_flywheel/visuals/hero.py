"""Optional HiggsField hero image — a branded backdrop behind single-image posts.

When the editorial orchestrator picks the IMAGE format (one punchy idea), we
generate a navy/violet abstract hero and composite the typographic card on top
of it (under a legibility scrim). Lifts production value on the posts that would
otherwise be the plainest, while the brand template keeps text consistent.

Gated on auth (`higgs.is_enabled()`); returns None when unconfigured or on any
failure so the render falls back to the flat-navy card. Never raises.
"""
from __future__ import annotations

from shared.logging.logger import AgentLogger

from . import higgs

_log = AgentLogger("visuals-hero")

# Image model: Nano Banana Pro — fast (~30s), ~2 credits, supports 4:5.
HERO_MODEL = "nano_banana_2"

# Every scene is wrapped so the result is always on-brand and text-safe:
# dark navy, blue->violet glow, no text/people/logos, lots of negative space
# (text gets composited over it, so the image must not compete).
_BRAND_ART = (
    "Dark navy (#0B1020) abstract background, premium minimal high-end SaaS "
    "tech aesthetic, soft blue-to-violet gradient glow (electric blue #0EA5E9 "
    "into violet #8B5CF6) bleeding from one corner, subtle geometric depth, "
    "clean, cinematic, lots of empty negative space for text. "
    "Absolutely no text, no words, no people, no faces, no logos, no UI. "
    "Subject motif: {scene}"
)


def is_enabled() -> bool:
    return higgs.is_enabled()


def hero_for(scene: str, *, aspect: str = "4:5") -> bytes | None:
    """Return a branded hero PNG for `scene`, or None when unconfigured/failed."""
    if not is_enabled():
        _log.log("hero_skipped_unauthed")
        return None
    prompt = _BRAND_ART.format(scene=(scene or "abstract data flow").strip()[:240])
    urls = higgs.generate_sync(
        HERO_MODEL, prompt,
        params={"aspect_ratio": aspect, "resolution": "2k"},
        wait_timeout="4m", timeout=300,
    )
    if not urls:
        _log.log("hero_no_result")
        return None
    png = higgs.download(urls[0])
    if png:
        _log.log("hero_rendered", metadata={"url": urls[0][:90]})
    return png
