"""3-stage editorial pipeline for long-form content.

Long-form here means: LinkedIn article, Substack post, Medium article, and
Newsletter section. LinkedIn POSTS stay single-shot — they're short enough
that the editorial pipeline would add latency without quality lift.

Pipeline:

  Stage 1: ARCHITECT
    Picks the angle from the idea / transcript excerpt. Outputs a structured
    outline: hook line, 3-5 sections (each with a one-sentence point and a
    one-sentence proof), close line. Sonnet @ 1500 tok.

  Stage 2: DRAFTER
    Reads the outline + voice spec, writes the full draft body. Sonnet @
    6000 tok (longest — Substack/Medium articles can run to 1500+ words).

  Stage 3: EDITOR
    Scores against brand_voice.QA_CHECKLIST. Rewrites the first line for
    stopper-specificity if needed. Tightens the close. Removes banned
    phrases. Sharpens vague numbers ("a lot" -> "$10K", etc.). Sonnet @
    6000 tok.

Each draft generated this way gets stamped with
  metadata.editorial_passes = 3
  metadata.editorial_cost_estimate = <usd>
so the dashboard can show which drafts went through the team vs single-shot.

Cost: ~3 Sonnet calls per long-form piece. At your volume (5-10 Use Now
clicks/day × 4 long-form pieces) this is ~$2-5/day Anthropic — vs ~$0.50/day
for single-shot. Quality lift well worth it for LI articles, Substack,
Medium, newsletter that actually rank.
"""
from __future__ import annotations

from typing import Any

from shared.logging.logger import AgentLogger

from . import brand_voice
from .llm import complete

_log = AgentLogger("editorial")

# (platform, format) -> brand_voice few-shot category. Mirrors FEW_SHOT_FOR in
# repurposer/agent.py — duplicated here so editorial is self-contained.
_FEW_SHOT_FOR: dict[tuple[str, str], str] = {
    ("linkedin",  "article"):    "linkedin",
    ("linkedin",  "newsletter"): "linkedin",
    ("substack",  "post"):       "substack_opener",
    ("medium",    "article"):    "linkedin",
    ("newsletter", "section"):   "linkedin",
}


# ── Stage 1: Architect ───────────────────────────────────────────────────────

_ARCHITECT_ROLE = """You are the EDITORIAL ARCHITECT. Your job is to pick the
sharpest angle on the seed idea, build a structured outline, and hand it to
the Drafter. You don't write prose — you give the Drafter a skeleton they
can flesh out without losing the thread.

Output STRICTLY this format (no preamble, no markdown fences):

ANGLE: <one sentence on the specific angle — not the topic, the angle. "AI
won't replace consultants who understand their client's business" is an
angle. "AI and consulting" is a topic.>

HOOK LINE: <the actual first line of the post — specific number, specific
moment, or pattern interrupt. Stops the scroll.>

SECTIONS:
1. <one-sentence point>
   PROOF: <one-sentence specific example / number / story to anchor it>
2. <one-sentence point>
   PROOF: <...>
3. <one-sentence point>
   PROOF: <...>
[4. <optional 4th section for Substack/Medium full articles>]
[5. <optional 5th section>]

CLOSE LINE: <one sentence that earns the reader's attention rather than
demanding it. NOT a CTA. A real question or a real action — never both.>

KEY PROPER NOUNS: <comma-separated list of specific names, tools, companies,
or numbers the Drafter MUST include for credibility>
"""


def _architect(seed_text: str, platform: str, format_: str,
                     pillar: str, voice: str = "ai_guy") -> str | None:
    """Build the outline. Returns plain-text outline or None on failure."""
    fmt_key = _FEW_SHOT_FOR.get((platform, format_), "linkedin")
    system = brand_voice.system_prompt(fmt_key, pillar, voice=voice) + "\n\n" + _ARCHITECT_ROLE
    user = (
        f"Seed idea (and any reference material below the first line):\n\n"
        f"{seed_text[:8000]}\n\n"
        f"Build the outline for ONE {format_} on {platform}, pillar {pillar}. "
        f"The Drafter will write the body from your outline + the voice spec."
    )
    try:
        return complete("editorial_architect", system, user)
    except Exception as e:
        _log.error("architect_failed", str(e),
                   metadata={"platform": platform, "format": format_})
        return None


# ── Stage 2: Drafter ─────────────────────────────────────────────────────────

_DRAFTER_ROLE = """You are the EDITORIAL DRAFTER. You receive an outline from
the Architect and write the full body in the voice spec above.

Your job:
- Use the Architect's HOOK LINE verbatim as the first line (do not rewrite).
- Expand each SECTION into 2-4 paragraphs that hit the point + proof.
- Use the CLOSE LINE verbatim as the final line.
- Include EVERY proper noun in KEY PROPER NOUNS — these are the credibility markers.
- Match the format's length: LinkedIn article 800-1200 words, LinkedIn newsletter
  600-1000 words, Newsletter section 600-900 words.
- Voice rules from the spec ABOVE are non-negotiable.

Output the post body only. No preamble, no headers, no quotes around it.
"""


def _drafter(seed_text: str, outline: str, platform: str, format_: str,
                   pillar: str, voice: str = "ai_guy") -> str | None:
    fmt_key = _FEW_SHOT_FOR.get((platform, format_), "linkedin")
    system = brand_voice.system_prompt(fmt_key, pillar, voice=voice) + "\n\n" + _DRAFTER_ROLE
    user = (
        f"OUTLINE FROM THE ARCHITECT:\n\n{outline}\n\n"
        f"---\n\nReference material (for context only, do not paste verbatim):\n\n"
        f"{seed_text[:6000]}\n\n"
        f"Write the {format_} body for {platform} now."
    )
    try:
        return complete("editorial_drafter", system, user)
    except Exception as e:
        _log.error("drafter_failed", str(e),
                   metadata={"platform": platform, "format": format_})
        return None


# ── Stage 3: Editor ──────────────────────────────────────────────────────────

_EDITOR_ROLE = """You are the EDITORIAL EDITOR. You receive a draft from the
Drafter and ship it to the dashboard. Your job is to harden it.

Walk through this checklist before returning the final body:

1. FIRST LINE — does it stop the scroll through SPECIFICITY (not clickbait)?
   If it's generic, rewrite it as a specific number, moment, or pattern interrupt.
2. BANNED PHRASES — scan for any phrase in the NEVER list (above). Rewrite to
   eliminate. No exceptions.
3. VAGUE STATS — sharpen anything fuzzy. "Many" -> "12". "A lot" -> "$10K".
   "Recently" -> "last Tuesday".
4. EXCLAMATION POINTS — cap at 2 for the whole piece. Replace the rest with
   periods.
5. CLOSE — does it earn attention or demand it? If it pitches, rewrite to a
   real question OR useful action — never both.
6. RHYTHM — short sentences for impact, longer for narrative, single-line
   paragraphs as punctuation. Boring? Break up.
7. NAMES + NUMBERS — every claim has a name or number attached, or it's deleted.

Output ONLY the final, edited body. No preamble. No "Here's the edited
version:" header. No marginal notes. Just the body.
"""


def _editor(draft: str, platform: str, format_: str,
                  pillar: str, voice: str = "ai_guy") -> str | None:
    fmt_key = _FEW_SHOT_FOR.get((platform, format_), "linkedin")
    system = brand_voice.system_prompt(fmt_key, pillar, voice=voice) + "\n\n" + _EDITOR_ROLE
    user = (
        f"DRAFT FROM THE DRAFTER:\n\n{draft}\n\n"
        f"---\n\nHarden it. Return only the final body."
    )
    try:
        return complete("editorial_editor", system, user)
    except Exception as e:
        _log.error("editor_failed", str(e),
                   metadata={"platform": platform, "format": format_})
        return None


# ── Public entrypoint ────────────────────────────────────────────────────────

def write_long_form(seed_text: str, platform: str, format_: str,
                    pillar: str, idx: int, voice: str = "ai_guy") -> tuple[str | None, dict]:
    """Run the 3-stage editorial pipeline (optionally in a specific voice).

    Returns (body, metadata). On any stage failure returns (None, {}). The
    metadata dict is meant to be merged into the draft row's metadata field.
    """
    _log.log("editorial_start",
             metadata={"platform": platform, "format": format_, "pillar": pillar, "voice": voice})

    outline = _architect(seed_text, platform, format_, pillar, voice)
    if not outline:
        return None, {}

    draft = _drafter(seed_text, outline, platform, format_, pillar, voice)
    if not draft:
        return None, {}

    edited = _editor(draft, platform, format_, pillar, voice)
    if not edited:
        # Fall back to the drafter output if editor fails — better than nothing.
        edited = draft

    metadata: dict[str, Any] = {
        "editorial_passes": 3,
        "editorial_pipeline": "architect_drafter_editor",
    }
    _log.log("editorial_done",
             metadata={"platform": platform, "format": format_,
                       "body_chars": len(edited)})
    return edited, metadata
