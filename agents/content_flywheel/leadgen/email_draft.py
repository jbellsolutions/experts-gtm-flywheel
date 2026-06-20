"""Custom offer-email drafting for enriched leads.

For each commenter we enriched, draft a personalised cold email built from:
their profile (name/headline/about) × their actual comment × the post they
commented on × the **offer framework** you maintains in the dashboard.

Single source of voice truth — reuses the brand voice + the LLM router. Returns
a {subject, body} pair the BDR (Morell) reviews and sends manually.
"""
from __future__ import annotations

import json

from shared.logging.logger import AgentLogger

from ..repurposer import brand_voice, voices
from ..repurposer.llm import complete

_log = AgentLogger("leadgen.email_draft")

_SCHEMA = '{"subject":"<email subject, <=70 chars, specific, no clickbait>","body":"<the email body>"}'


def _system(voice: str, framework: str, feedback: str | None = None) -> str:
    vp = voices.get(voice)
    identity = brand_voice.VOICE_DOC if voice == "ai_guy" else voices.SHARED_IDENTITY
    banned = ", ".join(brand_voice.BANNED_PHRASES + list(vp.extra_banned))
    rev = (f"REVISION — the previous draft wasn't right. Apply this feedback and improve it "
           f"(keep the opening rules):\n{feedback}\n\n" if feedback else "")
    return (
        f"{identity}\n\n{vp.voice_doc}\n\n"
        f"NEVER use these phrases or words: {banned}\n\n"
        "TASK: Write ONE custom cold outreach EMAIL to the person below for our offer. "
        "Follow the OFFER FRAMEWORK as the structure/spine of the email — do not invent a "
        "different offer. Make it specific to THIS person.\n\n"
        "OPENING LINE — special rules (ONLY the opening needs these; the rest of the email "
        "is already good, keep that style). Open by connecting with the SUBSTANCE of what "
        "they said, to build instant rapport. NEVER reference that they left a comment — "
        "never write 'your comment', 'your post', 'you commented', and never mention our "
        "post (the email may be sent from a teammate's inbox, so pointing at a LinkedIn "
        "comment is awkward and breaks trust). Saying you've been looking at their work / "
        "checking them out on LinkedIn is fine. Pick the mode that fits what they said:\n"
        "  1. PARAPHRASE their point as shared ground, no attribution — e.g. 'Steve, most "
        "people miss the reality that every offer basically acts like its own company.'\n"
        "  2. SOFT QUOTE if they have a memorable line, kept deliberately soft — e.g. "
        "'Kevin, I've been checking you out on LinkedIn and a few other places — I think it "
        "was you who said \"clarity creates momentum, complexity creates friction.\" That "
        "line stuck with me.'\n"
        "  3. NO strong line to work with → skip the hook and go STRAIGHT into the offer's "
        "core problem — e.g. 'There's a high-ticket clarity problem right now: most people "
        "selling AI work are stuck in the middle…'\n"
        "Then tie it to their role and deliver the offer per the framework. Warm, human, "
        "concise (4-8 short sentences), one clear soft call to action. No fabricated facts "
        "about them, and never invent a quote they didn't actually say.\n"
        f"OFFER FRAMEWORK (the offer + structure to follow):\n{framework or '(none provided — keep it a soft, relevant intro and ask)'}\n\n"
        f"{rev}"
        f"Return STRICT JSON only (no markdown, no preamble): {_SCHEMA}"
    )


def _user(lead: dict) -> str:
    return (
        f"PERSON: {lead.get('name') or '(name unknown)'}\n"
        f"HEADLINE / ROLE: {lead.get('headline') or '(unknown)'}\n"
        f"ABOUT: {(lead.get('about') or '')[:500]}\n"
        "WHAT THEY SAID (their own words — mine the SUBSTANCE for the opening per the rules; "
        "do NOT call it a 'comment' or frame it as a reply to a post):\n"
        f"{lead.get('comment_text') or '(nothing captured — use opening mode 3, straight into the offer)'}"
    )


def _parse(raw: str) -> dict | None:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = s.split("```")[1]
        if s.startswith("json"):
            s = s[4:]
    try:
        data = json.loads(s.strip())
        if isinstance(data, dict) and data.get("body"):
            return {"subject": str(data.get("subject", "")).strip(), "body": str(data["body"]).strip()}
    except Exception:  # noqa: BLE001
        if s:
            return {"subject": "", "body": s}
    return None


def draft_email(*, lead: dict, framework: str, voice: str = "ai_guy",
                feedback: str | None = None) -> dict | None:
    """Return {subject, body, flags} or None on failure. Opening references the
    substance of what the lead said (never 'your comment'/the post); body follows
    the offer framework. `feedback` (the Airtable Rerun box) revises a prior draft."""
    try:
        raw = complete("offer_email", _system(voice, framework, feedback), _user(lead))
    except Exception as e:  # noqa: BLE001
        _log.error("email_draft_failed", str(e), metadata={"lead": (lead.get("name") or "")[:60]})
        return None
    out = _parse(raw)
    if not out:
        return None
    ok, issues = brand_voice.passes_qa(out["body"])
    out["flags"] = issues or []
    return out
