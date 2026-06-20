"""LLM copy for post visuals — format decision + carousel/image slide copy.

Sync (mirrors editorial.py); called from the async visuals cron in its own
worker thread. Reuses the repurposer's voice doc + LLM dispatch so visuals
sound like you and route through model_config.
"""
from __future__ import annotations

import json

from ..repurposer import brand_voice
from ..repurposer.llm import complete


def _parse(raw: str) -> dict:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = s.split("```")[1]
        if s.startswith("json"):
            s = s[4:]
    try:
        return json.loads(s.strip())
    except Exception:
        return {}


def decide_format(post_body: str) -> tuple[str, str]:
    """The editorial orchestrator's call: (format, reason).

    Returns 'carousel' for multi-point/framework/how-to/list posts, 'image' for a
    single punchy idea (stat, quote, hot take, declaration) — with a short
    justification grounded in the post's structure and LinkedIn best practice.
    """
    system = (
        "You are the editorial orchestrator deciding the visual format for a "
        "LinkedIn post. Choose ONE:\n"
        "- CAROUSEL: the post has multiple points, steps, a framework, a numbered "
        "list, a how-to, or a before/after — worth swiping through (7-9 slides). "
        "Carousels win on depth + dwell time.\n"
        "- IMAGE: the post is one punchy idea — a single stat, quote, hot take, or "
        "one-line declaration. A single branded card hits harder than padding it "
        "into slides.\n"
        "Justify the call from the post's actual structure and what performs on "
        "LinkedIn. Return STRICT JSON only:\n"
        '{"format":"carousel|image","reason":"<1-2 sentences: why this format fits '
        'THIS post>"}'
    )
    data = _parse(complete("visual_format_decision", system, f"Post:\n\n{post_body[:2000]}"))
    fmt = (data.get("format") or "").lower()
    fmt = "carousel" if "carousel" in fmt else "image"
    reason = (data.get("reason") or "").strip()
    return fmt, reason


def decide_visual(post_body: str, *, allow_video: bool = False) -> dict:
    """Full editorial-orchestrator call: pick carousel | image | video + justify.

    Returns {"format": "...", "reason": "..."} and, for video,
    {"mode": "motion"|"concept", "motion_reason": "..."}. `video` is only offered
    when allow_video (HiggsField video is authed + enabled).
    """
    video_block = (
        "- VIDEO: the single strongest play when the idea is inherently visual or "
        "deserves motion to stop the scroll. Choose a mode:\n"
        "  - motion: animate our branded card (best default for a punchy single "
        "idea — premium motion beats a static card).\n"
        "  - concept: a conceptual b-roll clip for an idea that benefits from "
        "showing, not telling.\n"
        if allow_video else ""
    )
    fmt_enum = "carousel|image|video" if allow_video else "carousel|image"
    extra = (
        ',"mode":"motion|concept (only if format=video)","motion_reason":"<why this mode>"'
        if allow_video else ""
    )
    system = (
        "You are the editorial orchestrator choosing the visual for a LinkedIn "
        "post. Pick the ONE that performs best for THIS post:\n"
        "- CAROUSEL: multiple points, steps, a framework, a list, a how-to, or a "
        "before/after worth swiping (7-9 slides). Wins on depth + dwell.\n"
        "- IMAGE: one punchy idea — a single stat, quote, hot take, or one-line "
        "declaration. A single branded card hits harder than padding it out.\n"
        + video_block +
        "Justify from the post's actual structure and what performs on LinkedIn. "
        "If the post would genuinely benefit from motion — a demo, a dynamic or "
        "visual idea, something you'd want to SHOW moving rather than tell — "
        "choose video; don't default to a static card out of caution. Reserve "
        "carousel/image for posts that read better still. Return STRICT JSON only:\n"
        f'{{"format":"{fmt_enum}","reason":"<1-2 sentences>"{extra}}}'
    )
    data = _parse(complete("visual_format_decision", system, f"Post:\n\n{post_body[:2000]}"))
    fmt = (data.get("format") or "").lower()
    if "video" in fmt and allow_video:
        fmt = "video"
        mode = (data.get("mode") or "").lower()
        mode = "concept" if "concept" in mode else "motion"
        return {"format": "video", "reason": (data.get("reason") or "").strip(),
                "mode": mode, "motion_reason": (data.get("motion_reason") or "").strip()}
    fmt = "carousel" if "carousel" in fmt else "image"
    return {"format": fmt, "reason": (data.get("reason") or "").strip()}


def carousel_copy(post_body: str, pillar: str) -> list[dict]:
    """Return 7-9 structured slides (cover / point / cta) in your voice."""
    system = (
        brand_voice.VOICE_DOC
        + "\n\nYou are turning a LinkedIn post into a 7-9 slide carousel in "
        "your voice for a navy + blue-violet branded template.\n"
        "Rules:\n"
        "- Slide 1 = COVER: a scroll-stopping hook (specific, never clickbait). "
        "2-3 short headline lines.\n"
        "- Middle slides (5-7 of them) = POINT: ONE idea each. A short headline "
        "(2-5 words) plus 1-3 short body lines. Concrete, no fluff.\n"
        "- Final slide = CTA: tell the reader exactly what to do (follow for more, "
        "comment a question, save this).\n"
        "- Plain language, short lines, no banned phrases, no emoji. Fragments fine.\n"
        "Return STRICT JSON only (no markdown, no preamble):\n"
        '{"slides":[{"type":"cover|point|cta","eyebrow":"<=3 words or \\"\\"",'
        '"headline":["line",...],"body":["line",...]}]}\n'
        "Aim headline lines <= 22 chars and body lines <= 34 chars (they get "
        "re-fit to the template, so err shorter)."
    )
    raw = complete("visual_carousel_copy", system, f"Pillar {pillar} post:\n\n{post_body[:3000]}")
    data = _parse(raw)
    slides = data.get("slides") or []
    return [s for s in slides if isinstance(s, dict) and s.get("headline")]


def hero_prompt(post_body: str) -> str:
    """One short visual motif for the HiggsField hero backdrop (no text/people).

    The hero is an abstract brand backdrop the card sits on, so we only want a
    concrete *subject motif* — the art-direction wrapper (navy, gradient, no
    text/people) is added in hero.py. Keep it abstract and metaphorical, never
    literal screenshots or faces.
    """
    system = (
        "You art-direct an abstract background image for a LinkedIn post. "
        "Return ONE short visual motif (a metaphor for the post's idea) an image "
        "model can render. Abstract/conceptual only — flowing data, light, "
        "geometry, networks, circuitry, motion. NEVER text, words, people, "
        "faces, screenshots, or logos.\n"
        'Return STRICT JSON only: {"scene":"<8-16 words>"}'
    )
    data = _parse(complete("visual_hero_prompt", system, f"Post:\n\n{post_body[:1500]}"))
    return (data.get("scene") or "").strip()


def image_copy(post_body: str, pillar: str) -> dict:
    """Return one branded card: eyebrow + big headline + optional subhead."""
    system = (
        brand_voice.VOICE_DOC
        + "\n\nDistill this LinkedIn post into ONE branded card (single image) for "
        "a navy + blue-violet template.\n"
        "A short, punchy headline (the core idea / stat / hot take) in 2-4 lines, "
        "plus an optional one-line subhead. your voice. No banned phrases, no "
        "emoji.\n"
        "Return STRICT JSON only: "
        '{"eyebrow":"<=3 words or \\"\\"","headline":["line",...],"subhead":["line"]}\n'
        "Aim headline lines <= 18 chars (they get re-fit, so err shorter)."
    )
    raw = complete("visual_image_copy", system, f"Pillar {pillar} post:\n\n{post_body[:1800]}")
    data = _parse(raw)
    if not data.get("headline"):
        # last-ditch: first sentence of the post as the card
        first = (post_body.strip().split(".")[0] or "")[:80]
        data = {"eyebrow": "", "headline": [first], "subhead": []}
    return data
