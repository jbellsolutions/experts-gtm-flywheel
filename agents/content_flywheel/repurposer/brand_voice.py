"""Your brand voice — single source of truth for the content generator.

TEMPLATE FILE. Replace the placeholders below with YOUR brand's voice. The
onboarding assistant (see CLAUDE.md) fills these from a short interview — you
don't have to edit this by hand. Until it's filled the system still runs; it just
writes in a generic, safe voice.

Fill: VOICE_DOC (who you are + how you talk), BANNED_PHRASES (words you'd never
use), the two PILLAR angles, and FEW_SHOT_* (3-5 of your real best posts per
format — the generator learns your rhythm from these).
"""
from __future__ import annotations

from . import voices  # bank-backed VOICES registry (no cycle: voices doesn't import this)

VOICE_DOC = """
[TODO — your brand voice. Replace this whole block. The onboarding assistant will
draft it from a short interview; edit to taste.]

WHO YOU ARE: <one paragraph — your name, what you do, the experience that earns you
 the right to teach, and who you help do what.>

HOW YOU TALK (rate each 0-100): Formality <> · Authority <> · Warmth <> ·
 Humor <> · Vulnerability <> · Data-orientation <>

VOICE RULES:
- <e.g. first person singular; open with a story or a specific number, never a thesis>
- <e.g. short sentences for impact; concrete proper nouns + numbers, never vague>
- <e.g. no corporate speak, no false modesty, no hype>

WORDS YOU USE (sprinkle naturally): <your signature words/phrases>
"""

# Words/phrases the generator must NEVER use. These defaults are universal
# marketing-cliche bans — add your own pet-peeve words during onboarding.
BANNED_PHRASES = [
    "disrupt", "disruption", "thought leader", "game-changing", "game changer",
    "synergy", "synergize", "crushing it", "hustle", "guru", "ninja", "rockstar",
    "unlock", "unlocking", "excited to announce", "humbled", "let's unpack",
    "deep dive", "at the end of the day", "move the needle", "circle back",
    "low-hanging fruit", "best-in-class", "leverage", "supercharge", "revolutionize",
]

# Your two content angles. Pillar 1 = give value / help (no pitch). Pillar 2 =
# your journey / authority. Replace with your own.
PILLAR_1_HOOKS = [
    "[TODO — Pillar 1 hooks: genuinely helpful questions/openers, no pitch.]",
    "Example: What's the one workflow your team would automate first — and why haven't you?",
]

PILLAR_2_BEATS = [
    "[TODO — Pillar 2 beats: the story/authority points behind what you've built.]",
    "Example: Why I built <thing> after watching <person> lose <time> to <problem>.",
]

# 3-5 of YOUR best real posts per format. Tag each "1" (Pillar 1) or "2" (Pillar 2).
# The generator learns your rhythm from these — more + more diverse = better match.
FEW_SHOT_LINKEDIN = [
    ("1", """[TODO — paste a real Pillar 1 post of yours. Pattern: a specific claim ->
why it matters -> one genuine question OR useful action to close (not both).]"""),
    ("2", """[TODO — paste a real Pillar 2 post of yours. Pattern: a specific moment or
number -> what you actually did -> what it proves. Vulnerability from strength.]"""),
]

FEW_SHOT_SUBSTACK_OPENERS = [
    ("1", """[TODO — paste the first 2-3 paragraphs of a real long-form piece of yours.]"""),
]

# ── QA checklist (the system runs these against every draft before insert) ──

QA_CHECKLIST = [
    "Does it sound like a person talking, not a brand posting?",
    "Is there a specific number, tool, timeframe, or result mentioned?",
    "Would you actually say this out loud?",
    "Does it teach, solve, or show something real?",
    "Is the CTA a genuine question or useful action (not a sleazy funnel move)?",
    "Does it fit cleanly into Pillar 1 (just helping) or Pillar 2 (the journey)?",
    "Is it free of corporate buzzwords, hype language, and LinkedIn cliches?",
    "Could someone read this and walk away with something useful — even if they never buy?",
]

# ── System-prompt builder ─────────────────────────────────────────────────────

def system_prompt(format_name: str, pillar: str = "1", *,
                  voice: str = "ai_guy", cta: str | None = None) -> str:
    """Assemble a system prompt for a format + voice (+ optional pillar / CTA).

    `voice` selects one of the three bank-backed voices (voices.VOICES). `ai_guy`
    keeps the canonical persona (VOICE_DOC) + pillar nuance + the proven LinkedIn
    few-shots, enriched with the AI-Guy bank DNA. The POV voices (human_loop,
    ai_reality) use the shared identity + their own bank DNA and few-shots. When
    `cta` is given (the daily generator passes a rotated one), the post must end
    with that exact soft CTA; otherwise the original "question or action" close
    is kept (back-compat for the idea suggester).
    """
    vp = voices.get(voice)

    if voice == "ai_guy":
        identity = VOICE_DOC
        if pillar == "1":
            pillar_block = "PILLAR 1 — Help first (no pitch):\n  " + "\n  ".join(PILLAR_1_HOOKS)
            pillar_energy = (
                "Energy: generous, approachable, competent. Like a friend who's really good "
                "at this and genuinely wants to help. Implicit message: 'I'm not hiding "
                "anything. I'll tell you exactly what to do.'"
            )
        elif pillar == "2":
            pillar_block = "PILLAR 2 — The Journey (authority through the story):\n  " + "\n  ".join(PILLAR_2_BEATS)
            pillar_energy = (
                "Energy: proud, mission-driven, transparent. Like someone showing you around "
                "the operation they've built and genuinely believing in it. Implicit message: "
                "'This is real. These are real people doing real work.'"
            )
        else:
            pillar_block = "PILLAR — both (mix Pillar 1 helpfulness with Pillar 2 authority)"
            pillar_energy = "Blend the helpfulness of Pillar 1 with the credibility of Pillar 2."
        # proven LinkedIn few-shots (pillar-filtered) + a few builder examples from the bank
        examples = {"linkedin": FEW_SHOT_LINKEDIN,
                    "substack_opener": FEW_SHOT_SUBSTACK_OPENERS}.get(format_name, FEW_SHOT_LINKEDIN)
        base = [body for tag, body in examples if tag == pillar] or [b for _, b in examples]
        shots_list = base[:6] + (vp.few_shots[:3] if format_name == "linkedin" else [])
    else:
        identity = voices.SHARED_IDENTITY
        pillar_block = ""
        pillar_energy = ""
        shots_list = vp.few_shots

    voice_block = vp.voice_doc
    hedge = ("\n\n" + voices.HEDGE_RULE) if vp.hedge else ""
    shots = "\n\n---\n\n".join(shots_list)
    banned = ", ".join(BANNED_PHRASES + list(vp.extra_banned))

    if cta:
        close = (f"End with this exact call to action, rewritten in your own natural "
                 f"voice (do not paste it verbatim): {cta}")
    else:
        close = ("End with either a real question OR a useful action — not both.")

    return f"""{identity}

{voice_block}
{pillar_block}
{pillar_energy}{hedge}

NEVER use these phrases or words: {banned}

Examples of approved {format_name} posts in this voice (study the rhythm and
stance — never copy them):

{shots}

Now write ONE {format_name} post in this voice. The first line must make
someone stop scrolling through specificity (not clickbait). {close}

Output the post body only. No preamble, no explanation, no quotes around it.
"""


def passes_qa(body: str) -> tuple[bool, list[str]]:
    """Cheap pre-insert check. Returns (ok, reasons_failed)."""
    issues = []
    low = body.lower()
    for phrase in BANNED_PHRASES:
        if phrase in low:
            issues.append(f"contains banned phrase: '{phrase}'")
    if len(body.strip()) < 40:
        issues.append("too short")
    if body.count("!") > 3:
        issues.append("too many exclamation points (hype-y)")
    return (not issues, issues)
