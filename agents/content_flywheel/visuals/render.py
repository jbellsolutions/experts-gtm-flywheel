"""Render slide/card copy to PNG bytes via the brand SVG templates + cairosvg.

A Pillow text-measurement pass re-wraps any line that's too wide for its column
(the copy LLM aims short, but this guarantees nothing overflows regardless of
how the model sizes lines). Fonts resolve to the bundled static Inter weights
installed in Dockerfile.worker.
"""
from __future__ import annotations

import base64
import io
from functools import lru_cache
from pathlib import Path

from assets.brand import colors as C
from assets.brand import templates as T

_FONT_DIR = Path(__file__).resolve().parents[3] / "assets" / "brand" / "fonts"
_FONT_FILE = {900: "Inter-Black.ttf", 700: "Inter-Bold.ttf",
              600: "Inter-SemiBold.ttf", 400: "Inter-Regular.ttf"}
COLUMN = C.WIDTH - 2 * T.PAD  # 888px usable width


@lru_cache(maxsize=64)
def _font(weight: int, size: int):
    from PIL import ImageFont
    return ImageFont.truetype(str(_FONT_DIR / _FONT_FILE[weight]), size)


def _fit(lines, weight: int, size: int, max_px: int = COLUMN) -> list[str]:
    """Re-wrap each input line so its measured width never exceeds max_px."""
    out: list[str] = []
    f = _font(weight, size)
    for line in lines or []:
        line = (line or "").strip()
        if not line:
            continue
        if f.getlength(line) <= max_px:
            out.append(line)
            continue
        cur = ""
        for w in line.split():
            t = (cur + " " + w).strip()
            if f.getlength(t) <= max_px or not cur:
                cur = t
            else:
                out.append(cur)
                cur = w
        if cur:
            out.append(cur)
    return out


def _png(svg: str) -> bytes:
    import cairosvg
    out = io.BytesIO()
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=out,
                     output_width=C.WIDTH, output_height=C.HEIGHT)
    return out.getvalue()


def render_carousel(slides: list[dict], variant: dict | None = None) -> list[bytes]:
    total = len(slides)
    pngs: list[bytes] = []
    for i, s in enumerate(slides):
        typ = (s.get("type") or "point").lower()
        eyebrow = s.get("eyebrow") or None
        if typ == "cover":
            hl = _fit(s.get("headline", []), 900, 96)
            sub = _fit(s.get("body", []), 400, 38)
            svg = T.cover_slide(hl, sub, total, eyebrow=eyebrow, variant=variant)
        elif typ == "cta":
            hl = _fit(s.get("headline", []), 900, 70)
            body = _fit(s.get("body", []), 400, 38)
            svg = T.cta_slide(hl, body, i + 1, total, variant=variant)
        else:
            hl = _fit(s.get("headline", []), 700, 62)
            body = _fit(s.get("body", []), 400, 38)
            svg = T.point_slide(hl, body, i + 1, total, eyebrow=eyebrow, variant=variant)
        pngs.append(_png(svg))
    return pngs


def _data_uri(png: bytes | None) -> str | None:
    """Base64 PNG -> SVG <image href> data URI (cairosvg embeds it inline)."""
    if not png:
        return None
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def render_image(card: dict, hero: bytes | None = None, variant: dict | None = None) -> bytes:
    # The "left" composition indents text past a gradient rail (x = PAD+36), so it
    # has a narrower column than centered — fit to that width so a near-max line
    # can't run past the right margin.
    comp = (variant or {}).get("comp", "center")
    max_px = (C.WIDTH - (T.PAD + 36) - T.PAD) if comp == "left" else COLUMN
    hl = _fit(card.get("headline", []), 900, 90, max_px=max_px)
    sub = _fit(card.get("subhead", []), 400, 40, max_px=max_px)
    svg = T.image_card(hl, sub, eyebrow=card.get("eyebrow") or None,
                       bg_data_uri=_data_uri(hero), variant=variant)
    return _png(svg)


def render_overlay(card: dict, variant: dict | None = None) -> bytes:
    """Transparent text layer (PNG with alpha) to composite over a motion clip."""
    hl = _fit(card.get("headline", []), 900, 86)
    sub = _fit(card.get("subhead", []), 400, 38)
    svg = T.overlay_card(hl, sub, eyebrow=card.get("eyebrow") or None, variant=variant)
    return _png(svg)
