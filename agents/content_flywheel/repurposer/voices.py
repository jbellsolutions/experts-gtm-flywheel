"""Voice registry for the multi-voice LinkedIn engine.

Each voice is backed by a markdown bank under `voice_banks/` (Voice DNA + CTA DNA
+ post directions). We parse those at import time so the banks stay the single,
editable source of truth — voice docs, few-shots, and CTA banks all derive from
the markdown rather than being duplicated here.

TEMPLATE: ships with three example voice slots, posted one per day. Fill at least
the primary one (your brand voice) during onboarding; the two secondary angles
are optional. You can collapse to a single voice if you prefer.
- ai_guy      — your PRIMARY voice (helpful, specific, generous).
- human_loop  — secondary angle A (a contrasting POV — customize or drop).
- ai_reality  — secondary angle B (another angle — customize or drop).

`brand_voice.system_prompt(...)` consumes this module; it owns the shared identity,
banned-phrase list, and QA. (No import of brand_voice here — avoids a cycle.)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_BANK_DIR = Path(__file__).resolve().parent / "voice_banks"

# Shared identity prepended to the POV voices (ai_guy uses the fuller VOICE_DOC
# in brand_voice). Keeps every voice unmistakably yours, plain-spoken, no hype.
SHARED_IDENTITY = (
    "You are <THE EXPERT> — a credible operator in your field posting "
    "on LinkedIn. You are plain-spoken, specific, and generous. You write like a "
    "person talking, not a brand posting: short sentences, real numbers, real "
    "workflows, no hype, no guru voice. You are pro-AI and practical — the value "
    "is always in implementation, ownership, and judgment, never in magic."
)

# Business categories the daily generator rotates through so posts stay varied
# and concrete (the trend gets framed as a use case for one of these).
INDUSTRIES = [
    "legal / law firms", "healthcare & clinics", "finance & accounting",
    "real estate", "e-commerce & retail", "recruiting & staffing",
    "marketing agencies", "logistics & supply chain", "manufacturing",
    "SaaS & startups", "construction & trades", "insurance",
    "professional services / consulting", "hospitality & restaurants",
    "education & training", "nonprofits",
]

# Fallback CTAs (used when a bank has no explicit CTA DNA, e.g. human_loop).
DEFAULT_CTAS = [
    "Drop a comment with the situation you're working through and I'll tell you "
    "how I'd approach it.",
    "If this resonates, repost it so it reaches someone who needs to see it.",
    "If you'd rather not share the details publicly, DM me or connect — tell me "
    "what you're working on and I'll give you a straight answer.",
]


@dataclass(frozen=True)
class VoiceProfile:
    id: str
    name: str
    voice_doc: str                 # the voice-specific DNA block
    few_shots: list[str]           # curated exemplar directions from the bank
    cta_bank: list[str]            # rotating soft CTAs (comment/repost/dm)
    hedge: bool = False            # ai_reality: frame predictions as plausible risks
    extra_banned: list[str] = field(default_factory=list)


# ── bank parsing ─────────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _bullets(md: str, header: str) -> list[str]:
    """Lines of a `- ` bullet list under a `## <header>` section."""
    # prefix match so "## Voice DNA From The Reference" matches header "Voice DNA"
    m = re.search(rf"^##\s+{re.escape(header)}[^\n]*$(.*?)(?=^##\s|\Z)", md,
                  re.M | re.S)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("- "):
            out.append(line[2:].strip())
    return out


def _directions(md: str) -> list[str]:
    """Bodies of the `### N. Title` sections under the 50-directions header."""
    sec = re.search(
        r"^##\s+50 Original LinkedIn-Ready Post Directions\s*$(.*?)(?=^##\s|\Z)",
        md, re.M | re.S)
    if not sec:
        return []
    body = sec.group(1)
    out = []
    for block in re.split(r"^###\s+\d+\.\s+.*$", body, flags=re.M)[1:]:
        text = block.strip()
        if text:
            out.append(text)
    return out


def _curated(items: list[str], n: int = 9) -> list[str]:
    """A spread of `n` items across the list (variety, not just the first few)."""
    if len(items) <= n:
        return items
    step = max(1, len(items) // n)
    return items[::step][:n]


@lru_cache(maxsize=1)
def _banks() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for vid in ("ai_guy", "human_loop", "ai_reality"):
        md = _read(_BANK_DIR / f"{vid}.md")
        out[vid] = {
            "voice_dna": _bullets(md, "Voice DNA"),
            "cta_dna": _bullets(md, "CTA DNA"),
            "directions": _directions(md),
        }
    return out


def _voice_dna_block(vid: str, intro: str) -> str:
    dna = _banks()[vid]["voice_dna"]
    lines = "\n".join(f"- {b}" for b in dna)
    return f"{intro}\n\nVOICE DNA (write to these):\n{lines}" if lines else intro


# ── registry ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _registry() -> dict[str, VoiceProfile]:
    b = _banks()

    ai_guy = VoiceProfile(
        id="ai_guy", name="Primary",
        voice_doc=_voice_dna_block(
            "ai_guy",
            "VOICE: your primary voice (example — the onboarding assistant customizes this "
            "from your brand voice). The operator in the trenches. You share what works, "
            "explain what breaks, and give away frameworks, tools, and decision "
            "rules without hiding the ball. You talk in workflow language: inputs, "
            "outputs, approvals, edge cases, ownership, logging, maintenance. An "
            "agent is a workflow, not a prompt. First-person credibility — you've "
            "built and tested this."),
        few_shots=_curated(b["ai_guy"]["directions"]),
        cta_bank=b["ai_guy"]["cta_dna"] or DEFAULT_CTAS,
    )

    human_loop = VoiceProfile(
        id="human_loop", name="Secondary angle A (example — customize)",
        voice_doc=_voice_dna_block(
            "human_loop",
            "VOICE: Human-in-the-Loop / AI Reality. Your thesis: AI spend, agents, "
            "and new tools do not create business outcomes by themselves. The "
            "missing piece is a trained, accountable human operator and a "
            "*designed* loop. Open with a concrete number or observed story, name "
            "the hidden problem (no owner, no designed loop), use a simple analogy, "
            "challenge the 'AI replaces people' narrative without being anti-AI, and "
            "end on a thoughtful implication or genuine question."),
        few_shots=_curated(b["human_loop"]["directions"]),
        cta_bank=b["human_loop"]["cta_dna"] or DEFAULT_CTAS,
    )

    ai_reality = VoiceProfile(
        id="ai_reality", name="Secondary angle B (example — customize)",
        voice_doc=_voice_dna_block(
            "ai_reality",
            "VOICE: AI Reality-Check / Stay Agnostic. Pro-AI, but clear-eyed about "
            "cost, lock-in, subsidy, and provider risk. Companies should not build "
            "the whole business on one model, one lab, one platform, or one pricing "
            "assumption. Be model-, platform-, and company-agnostic; keep data "
            "portable; test open and local; don't outsource domain expertise or "
            "cognition — stay the expert and let AI build *with* you. ALWAYS name a "
            "risk, then give the constructive next move. Never doom."),
        few_shots=_curated(b["ai_reality"]["directions"]),
        cta_bank=b["ai_reality"]["cta_dna"] or DEFAULT_CTAS,
        hedge=True,
    )

    return {"ai_guy": ai_guy, "human_loop": human_loop, "ai_reality": ai_reality}


VOICES = _registry()

# Daily posting order — AI Guy leads in the morning.
DAILY_ORDER = ["ai_guy", "human_loop", "ai_reality"]

HEDGE_RULE = (
    "IMPORTANT: never present future pricing, IPO timing, rate-limit changes, or "
    "vendor strategy as guaranteed. Frame them as plausible business risks to plan "
    "around (\"could,\" \"may,\" \"don't assume it stays this way\")."
)


def get(voice_id: str) -> VoiceProfile:
    return VOICES.get(voice_id) or VOICES["ai_guy"]
