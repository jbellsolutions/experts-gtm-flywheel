"""On-demand outreach generator for the VA prospecting tool.

Given a prospect (industry/role) and the specific post / conversation, generate
on-voice outreach for one of several channels — LinkedIn comment, cold DM,
connection-request note, DM reply, email, or SMS — in your your brand brand
voice. The win formula is reused: voice × the specific prospect/industry × the
specific post/conversation. The VA reviews + sends manually.

Reuses the 3-voice source of truth (brand_voice.VOICE_DOC + voices.VOICES +
BANNED_PHRASES) and the LLM router. Composes its own JSON-output system prompt
(rather than brand_voice.system_prompt, which is tuned for single-post output)
so it can return N structured variants per call.
"""
from __future__ import annotations

import json
import os

import httpx

from shared.logging.logger import AgentLogger

from ..repurposer import brand_voice, voices
from ..repurposer.llm import complete

_log = AgentLogger("prospecting")
_FIRECRAWL_SCRAPE = "https://api.firecrawl.dev/v1/scrape"

# Per-channel shaping. `needs` lists which context fields matter for the prompt.
CHANNELS: dict[str, dict] = {
    "comment": {
        "label": "LinkedIn comment",
        "rule": ("Write a LinkedIn COMMENT (2-4 short sentences) reacting to the "
                 "SPECIFIC post below. Add one genuine, specific insight or a real "
                 "question that proves you read it. Never 'great post', never a "
                 "pitch, never self-promotion. Sound like a sharp peer."),
        "needs_post": True,
    },
    "cold_dm": {
        "label": "Cold DM / first message",
        "rule": ("Write a first LinkedIn DM (3-5 short sentences) to this prospect. "
                 "Reference something specific about them, their role, or their "
                 "industry. Be warm and genuinely useful. No hard pitch. End with "
                 "one light, easy-to-answer question."),
    },
    "connection_note": {
        "label": "Connection-request note",
        "rule": ("Write a LinkedIn connection-request note. HARD LIMIT 280 "
                 "characters. Warm, specific to this prospect, with a real reason "
                 "to connect. No pitch, no link."),
        "max_chars": 280,
    },
    "dm_reply": {
        "label": "DM reply (in thread)",
        "rule": ("Continue the LinkedIn DM thread below as your next message. "
                 "Natural, helpful, moves it forward. Match the thread's tone and "
                 "answer what they actually said. No pitch unless they asked."),
        "needs_thread": True,
    },
    "email": {
        "label": "Email",
        "rule": ("Write a cold outreach EMAIL. Return a subject (<=60 chars, "
                 "specific, no clickbait) and a body (4-8 short sentences, "
                 "personalized to the prospect, one clear soft call to action)."),
        "email": True,
    },
    "sms": {
        "label": "SMS",
        "rule": ("Write a prospecting SMS. HARD LIMIT 320 characters. Casual, one "
                 "clear line, like a text from a helpful person — not a marketer. "
                 "No links unless essential."),
        "max_chars": 320,
    },
}


def scrape(url: str) -> str | None:
    """Best-effort Firecrawl scrape of a URL -> markdown text. LinkedIn is often
    login-walled, so this may return thin/no content; the caller falls back to
    pasted text in that case."""
    key = os.getenv("FIRECRAWL_API_KEY")
    if not key or not url:
        return None
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(_FIRECRAWL_SCRAPE,
                       headers={"Authorization": f"Bearer {key}",
                                "Content-Type": "application/json"},
                       json={"url": url, "formats": ["markdown"]})
            r.raise_for_status()
            md = (((r.json() or {}).get("data") or {}).get("markdown") or "").strip()
            return md[:4000] or None
    except Exception as e:  # noqa: BLE001
        _log.error("scrape_failed", str(e), metadata={"url": url[:80]})
        return None


def _system(channel: str, voice: str) -> str:
    cfg = CHANNELS[channel]
    vp = voices.get(voice)
    identity = brand_voice.VOICE_DOC if voice == "ai_guy" else voices.SHARED_IDENTITY
    banned = ", ".join(brand_voice.BANNED_PHRASES + list(vp.extra_banned))
    schema = ('{"variants":[{"subject":"<email subject; \\"\\" for non-email>",'
              '"text":"<the message>"}]}')
    return (
        f"{identity}\n\n{vp.voice_doc}\n\n"
        f"NEVER use these phrases or words: {banned}\n\n"
        f"TASK: {cfg['rule']}\n\n"
        "Write as you reaching out to a real person — specific to THEIR world "
        "(role, industry, and what they posted/said), never generic. Produce 3 "
        "DISTINCT variants.\n"
        f"Return STRICT JSON only (no markdown, no preamble): {schema}"
    )


def _user(channel: str, prospect: str, post: str, thread: str) -> str:
    cfg = CHANNELS[channel]
    parts = [f"PROSPECT (who you're writing to):\n{prospect or '(not provided)'}"]
    if cfg.get("needs_thread"):
        parts.append(f"\nCONVERSATION SO FAR (most recent last):\n{thread or '(none)'}")
    elif cfg.get("needs_post"):
        parts.append(f"\nTHE POST to react to:\n{post or '(not provided)'}")
    elif post:
        parts.append(f"\nRELEVANT CONTEXT (a recent post/article of theirs):\n{post}")
    if cfg.get("max_chars"):
        parts.append(f"\nEach variant MUST be <= {cfg['max_chars']} characters.")
    return "\n".join(parts)


def _parse(raw: str) -> list[dict]:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = s.split("```")[1]
        if s.startswith("json"):
            s = s[4:]
    try:
        data = json.loads(s.strip())
        out = data.get("variants") if isinstance(data, dict) else data
        return [v for v in (out or []) if isinstance(v, dict) and v.get("text")]
    except Exception:
        # last-ditch: treat the whole thing as one variant
        return [{"subject": "", "text": s}] if s else []


def generate(channel: str, *, voice: str = "ai_guy", prospect: str = "",
             post: str = "", thread: str = "") -> dict:
    """Return {channel, label, voice, variants:[{subject?, text, flags}]}."""
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel {channel!r}")
    cfg = CHANNELS[channel]
    system = _system(channel, voice)
    user = _user(channel, prospect, post, thread)
    raw = complete("prospect_draft", system, user)
    variants = _parse(raw)
    # QA + length flags per variant (advisory — VA still reviews).
    cap = cfg.get("max_chars")
    for v in variants:
        text = v.get("text", "")
        ok, issues = brand_voice.passes_qa(text)
        v["flags"] = (issues or []) + (
            [f"over {cap} chars ({len(text)})"] if cap and len(text) > cap else [])
        v["chars"] = len(text)
    return {"channel": channel, "label": cfg["label"], "voice": voice,
            "is_email": bool(cfg.get("email")), "variants": variants[:3]}
