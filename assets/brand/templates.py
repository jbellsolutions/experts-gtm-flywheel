"""SVG builders for the carousel/image visual system.

Each function returns a complete 1080x1350 SVG string for cairosvg to rasterize.
Copy arrives as pre-wrapped lines (the copy LLM + a Pillow fit-check guarantee
each line fits its column), so these builders just position text — no wrapping.
"""
from __future__ import annotations

from . import colors as C

PAD = 96
CX = C.WIDTH // 2

# ── visual variants ──────────────────────────────────────────────────────────
# A "variant" rotates the look between posts (palette / gradient angle / bg
# treatment / composition) while staying on-brand. visuals/variant.py curates the
# set and round-robins it; templates just consume the chosen dict. variant=None
# everywhere reproduces the original look EXACTLY (so nothing regresses).
_DEFAULT_VARIANT = {
    "key": "classic",
    "grad": (C.GRAD_START, C.GRAD_MID, C.GRAD_END),  # sky → blue → violet
    "angle": "horiz",                                # gradient direction
    "bg": "glow-top",                                # navy background treatment
    "comp": "center",                                # image-card composition
}
_ANGLE = {  # x1,y1,x2,y2 for the brand linear gradient
    "horiz": (0, 0, 1, 0.25),
    "diag":  (0, 0, 1, 1),
    "vert":  (0, 0, 0, 1),
}
_GLOW = {  # cx,cy,r for the radial glow (where the light pools)
    "glow-top":    (0.5, 0, 0.75),
    "glow-corner": (0.85, 0.06, 0.85),
    "split":       (0.5, 0, 0.75),
    "mesh":        (0.5, 0, 0.75),
}


def _v(variant) -> dict:
    """Fill any missing keys from the default so a partial variant is safe."""
    if not variant:
        return _DEFAULT_VARIANT
    return {**_DEFAULT_VARIANT, **variant}


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _defs(variant=None) -> str:
    v = _v(variant)
    g0, g1, g2 = v["grad"]
    x1, y1, x2, y2 = _ANGLE.get(v["angle"], _ANGLE["horiz"])
    gx, gy, gr = _GLOW.get(v["bg"], _GLOW["glow-top"])
    return (
        '<defs>'
        f'<linearGradient id="brand" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">'
        f'<stop offset="0" stop-color="{g0}"/>'
        f'<stop offset="0.5" stop-color="{g1}"/>'
        f'<stop offset="1" stop-color="{g2}"/>'
        '</linearGradient>'
        f'<radialGradient id="glow" cx="{gx}" cy="{gy}" r="{gr}">'
        f'<stop offset="0" stop-color="{C.NAVY_GLOW}" stop-opacity="0.16"/>'
        f'<stop offset="0.6" stop-color="{C.NAVY_GLOW}" stop-opacity="0"/>'
        '</radialGradient>'
        # Faint dot texture for the bg="mesh" treatment (no-op unless painted).
        '<pattern id="mesh" width="46" height="46" patternUnits="userSpaceOnUse">'
        f'<circle cx="3" cy="3" r="2.4" fill="{C.NAVY_GLOW}" fill-opacity="0.10"/>'
        '</pattern>'
        # Legibility scrim for when a hero image is the background: darken top
        # (wordmark) + bottom (handle/counter) + a soft overall wash so white
        # text always reads, while the hero stays visible through the middle.
        f'<linearGradient id="scrim" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{C.NAVY}" stop-opacity="0.86"/>'
        f'<stop offset="0.32" stop-color="{C.NAVY}" stop-opacity="0.5"/>'
        f'<stop offset="0.7" stop-color="{C.NAVY}" stop-opacity="0.5"/>'
        f'<stop offset="1" stop-color="{C.NAVY}" stop-opacity="0.9"/>'
        '</linearGradient>'
        '</defs>'
    )


def _lines(lines, x, top, size, weight, fill, lh, anchor="start"):
    """A <text> block: first baseline at `top`, each line `lh` below the prior."""
    if not lines:
        return ""
    spans = "".join(
        f'<tspan x="{x}" dy="{0 if i == 0 else lh}">{_esc(ln)}</tspan>'
        for i, ln in enumerate(lines)
    )
    return (
        f'<text x="{x}" y="{top}" font-family="{C.FONT}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" '
        f'xml:space="preserve">{spans}</text>'
    )


def _frame(faint_wordmark: bool = False, bg_data_uri: str | None = None,
           transparent: bool = False, variant=None) -> str:
    """Navy bg (or a hero image + scrim) + top gradient bar + glow + wordmark.

    When `bg_data_uri` is given (a base64 PNG data URI from a HiggsField hero),
    the flat navy fill is replaced by the full-bleed hero under a legibility
    scrim, so white text stays readable. The gradient bar/glow/wordmark stay.

    When `transparent` is True, no background is drawn at all — the canvas stays
    transparent so the frame can be composited (via ffmpeg) on top of a moving
    HiggsField video. Only the brand bar + wordmark render.
    """
    wm_fill = C.TEXT_FAINT if faint_wordmark else C.TEXT_MUTED
    if transparent:
        bg = ""
    elif bg_data_uri:
        bg = (
            f'<image href="{bg_data_uri}" x="0" y="0" width="{C.WIDTH}" '
            f'height="{C.HEIGHT}" preserveAspectRatio="xMidYMid slice"/>'
            f'<rect width="{C.WIDTH}" height="{C.HEIGHT}" fill="url(#scrim)"/>'
        )
    else:
        treat = _v(variant)["bg"]
        navy = f'<rect width="{C.WIDTH}" height="{C.HEIGHT}" fill="{C.NAVY}"/>'
        glow = f'<rect width="{C.WIDTH}" height="{C.HEIGHT}" fill="url(#glow)"/>'
        if treat == "split":
            # a faint diagonal brand wash over navy instead of the radial glow.
            bg = navy + f'<rect width="{C.WIDTH}" height="{C.HEIGHT}" fill="url(#brand)" fill-opacity="0.10"/>'
        elif treat == "mesh":
            bg = navy + f'<rect width="{C.WIDTH}" height="{C.HEIGHT}" fill="url(#mesh)"/>' + glow
        else:  # glow-top (default) / glow-corner — radial glow, position set in _defs
            bg = navy + glow
    return (
        bg
        + f'<rect x="0" y="0" width="{C.WIDTH}" height="10" fill="url(#brand)"/>'
        f'<circle cx="{PAD + 9}" cy="{104}" r="9" fill="url(#brand)"/>'
        f'<text x="{PAD + 30}" y="{114}" font-family="{C.FONT}" font-size="27" '
        f'font-weight="{C.W_SEMI}" fill="{wm_fill}" letter-spacing="3">'
        f'{_esc(C.WORDMARK)}</text>'
    )


def _counter(num: int, total: int) -> str:
    return (
        f'<text x="{PAD}" y="{C.HEIGHT - 72}" font-family="{C.FONT}" '
        f'font-size="26" font-weight="{C.W_SEMI}" fill="{C.TEXT_FAINT}">'
        f'{num:02d} / {total:02d}</text>'
    )


def _svg(body: str, variant=None) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{C.WIDTH}" '
        f'height="{C.HEIGHT}" viewBox="0 0 {C.WIDTH} {C.HEIGHT}">'
        f'{_defs(variant)}{body}</svg>'
    )


def cover_slide(headline, subhead, total, eyebrow=None, bg_data_uri=None, variant=None):
    """Slide 1 — the hook. Big white headline + gradient accent + subhead.

    `bg_data_uri` (optional) puts a HiggsField hero behind the cover under a scrim.
    `variant` (optional) rotates palette/bg; all `url(#brand)` accents recolor.
    """
    parts = [_frame(bg_data_uri=bg_data_uri, variant=variant)]
    y = 470
    if eyebrow:
        parts.append(_lines([eyebrow.upper()], PAD, 300, 30, C.W_BOLD, "url(#brand)", 0))
    parts.append(f'<rect x="{PAD}" y="{y - 96}" width="120" height="9" rx="4" fill="url(#brand)"/>')
    parts.append(_lines(headline, PAD, y, 96, C.W_BLACK, C.WHITE, 106))
    if subhead:
        sub_top = y + 106 * max(0, len(headline) - 1) + 150
        parts.append(_lines(subhead, PAD, sub_top, 38, C.W_REG, C.TEXT_LIGHT, 50))
    parts.append(_counter(1, total))
    parts.append(
        f'<text x="{C.WIDTH - PAD}" y="{C.HEIGHT - 72}" font-family="{C.FONT}" '
        f'font-size="26" font-weight="{C.W_BOLD}" fill="url(#brand)" '
        f'text-anchor="end">swipe →</text>'
    )
    return _svg("".join(parts), variant)


def point_slide(headline, body, num, total, eyebrow=None, variant=None):
    """A value slide — one idea. Gradient eyebrow, bold headline, light body."""
    parts = [_frame(faint_wordmark=True, variant=variant)]
    if eyebrow:
        parts.append(_lines([eyebrow.upper()], PAD, 300, 28, C.W_BOLD, "url(#brand)", 0))
    parts.append(_lines(headline, PAD, 410, 62, C.W_BOLD, C.WHITE, 74))
    body_top = 410 + 74 * max(0, len(headline) - 1) + 150
    parts.append(_lines(body, PAD, body_top, 38, C.W_REG, C.TEXT_LIGHT, 56))
    parts.append(_counter(num, total))
    return _svg("".join(parts), variant)


def cta_slide(headline, body, num, total, cta=None, variant=None):
    """Last slide — the call to action: headline + gradient pill button."""
    cta = cta or C.CTA_DEFAULT
    parts = [_frame(variant=variant)]
    parts.append(_lines(headline, PAD, 470, 70, C.W_BLACK, C.WHITE, 82))
    body_top = 470 + 82 * max(0, len(headline) - 1) + 150
    if body:
        parts.append(_lines(body, PAD, body_top, 38, C.W_REG, C.TEXT_LIGHT, 54))
    pill_y = 1080
    pill_w = min(C.WIDTH - 2 * PAD, 40 + len(cta) * 26)
    parts.append(f'<rect x="{PAD}" y="{pill_y}" width="{pill_w}" height="84" rx="42" fill="url(#brand)"/>')
    parts.append(
        f'<text x="{PAD + pill_w // 2}" y="{pill_y + 54}" font-family="{C.FONT}" '
        f'font-size="32" font-weight="{C.W_BOLD}" fill="{C.NAVY}" '
        f'text-anchor="middle">{_esc(cta)}</text>'
    )
    parts.append(_counter(num, total))
    return _svg("".join(parts), variant)


def image_card(headline, subhead, eyebrow=None, bg_data_uri=None, variant=None):
    """Single branded card — hook for image-format posts.

    `bg_data_uri` (optional) puts a HiggsField hero behind the text under a scrim.
    `variant` rotates palette/bg and the composition: "center" (centered hook +
    accent bar, the original) or "left" (left-aligned hook on a gradient rail).
    """
    v = _v(variant)
    parts = [_frame(bg_data_uri=bg_data_uri, variant=variant)]
    n = len(headline)

    if v["comp"] == "left":
        hx = PAD + 36                      # text sits just past the rail
        top = 600 - (n - 1) * 30
        if eyebrow:
            parts.append(
                f'<text x="{hx}" y="{top - 86}" font-family="{C.FONT}" font-size="30" '
                f'font-weight="{C.W_BOLD}" fill="url(#brand)" letter-spacing="3">'
                f'{_esc(eyebrow.upper())}</text>'
            )
        rail_h = max(102 * n, 110)
        parts.append(
            f'<rect x="{PAD}" y="{top - 78}" width="10" height="{rail_h}" rx="5" '
            f'fill="url(#brand)"/>'
        )
        parts.append(_lines(headline, hx, top, 90, C.W_BLACK, C.WHITE, 102))
        if subhead:
            sub_top = top + 102 * (n - 1) + 150
            parts.append(_lines(subhead, hx, sub_top, 40, C.W_REG, C.TEXT_LIGHT, 56))
        handle_anchor, handle_x = "start", PAD
    else:  # center (original geometry, unchanged)
        if eyebrow:
            parts.append(
                f'<text x="{CX}" y="380" font-family="{C.FONT}" font-size="30" '
                f'font-weight="{C.W_BOLD}" fill="url(#brand)" text-anchor="middle" '
                f'letter-spacing="3">{_esc(eyebrow.upper())}</text>'
            )
        top = 690 - (n - 1) * 50
        parts.append(_lines(headline, CX, top, 90, C.W_BLACK, C.WHITE, 102, anchor="middle"))
        parts.append(f'<rect x="{CX - 70}" y="{top + 102 * (n - 1) + 70}" width="140" height="9" rx="4" fill="url(#brand)"/>')
        if subhead:
            sub_top = top + 102 * (n - 1) + 160
            parts.append(_lines(subhead, CX, sub_top, 40, C.W_REG, C.TEXT_LIGHT, 56, anchor="middle"))
        handle_anchor, handle_x = "middle", CX

    parts.append(
        f'<text x="{handle_x}" y="{C.HEIGHT - 110}" font-family="{C.FONT}" font-size="28" '
        f'font-weight="{C.W_SEMI}" fill="{C.TEXT_MUTED}" text-anchor="{handle_anchor}" '
        f'letter-spacing="3">{_esc(C.HANDLE)}</text>'
    )
    return _svg("".join(parts), variant)


def overlay_card(headline, subhead, eyebrow=None, variant=None):
    """Transparent text layer to composite (ffmpeg) over a moving HiggsField clip.

    Reuses image_card's proven centered geometry (no overlap for multi-line
    headlines) but with NO navy background — instead a full-frame legibility wash
    + top/bottom scrim so white text reads while the motion still shows through.
    `variant` only recolors the gradient accents so the overlay matches its anchor
    card; geometry stays centered for legibility over motion.
    """
    parts = [_frame(transparent=True, variant=variant)]
    # full-frame wash (hero stays ~60% visible) + bottom/top scrim for contrast.
    parts.append(f'<rect width="{C.WIDTH}" height="{C.HEIGHT}" fill="{C.NAVY}" fill-opacity="0.42"/>')
    parts.append(f'<rect width="{C.WIDTH}" height="{C.HEIGHT}" fill="url(#scrim)"/>')
    if eyebrow:
        parts.append(
            f'<text x="{CX}" y="380" font-family="{C.FONT}" font-size="30" '
            f'font-weight="{C.W_BOLD}" fill="url(#brand)" text-anchor="middle" '
            f'letter-spacing="3">{_esc(eyebrow.upper())}</text>'
        )
    n = len(headline)
    top = 690 - (n - 1) * 50
    parts.append(_lines(headline, CX, top, 90, C.W_BLACK, C.WHITE, 102, anchor="middle"))
    parts.append(f'<rect x="{CX - 70}" y="{top + 102 * (n - 1) + 70}" width="140" height="9" rx="4" fill="url(#brand)"/>')
    if subhead:
        sub_top = top + 102 * (n - 1) + 160
        parts.append(_lines(subhead, CX, sub_top, 40, C.W_REG, C.TEXT_LIGHT, 56, anchor="middle"))
    parts.append(
        f'<text x="{CX}" y="{C.HEIGHT - 110}" font-family="{C.FONT}" font-size="28" '
        f'font-weight="{C.W_SEMI}" fill="{C.TEXT_LIGHT}" text-anchor="middle" '
        f'letter-spacing="3">{_esc(C.HANDLE)}</text>'
    )
    return _svg("".join(parts), variant)
