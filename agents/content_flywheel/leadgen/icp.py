"""ICP filtering for scraped commenters.

Two gates, ordered cheapest-first to control spend:

  1. prefilter(comment_text)  — FREE heuristic, runs BEFORE any /profile credit.
     Drops low-signal commenters (emoji-only, "great post!", bots) so we only
     pay to fetch a headline for plausible people.

  2. score_lead(headline, about) — keyword score on the headline (free); an LLM
     tiebreak (`complete("lead_icp", ...)`, Haiku) only for the borderline band.

your ICP for this engine: legal/legal-ops, AI agencies & consultancies,
founders/CEOs, and ops/CTO/automation buyers.
"""
from __future__ import annotations

import json
import re
from typing import Any

from shared.logging.logger import AgentLogger

from ..repurposer.llm import complete

_log = AgentLogger("leadgen.icp")

# Headline keyword groups → ICP signal.
ICP_KEYWORDS: dict[str, list[str]] = {
    "legal": ["legal", "lawyer", "attorney", "counsel", "law firm", "paralegal", "litigation", "compliance"],
    "agency": ["agency", "consultancy", "consultant", "automation", "ai studio", "systems integrator",
               "solutions architect", "agentic", "ai agency"],
    "founder": ["founder", "co-founder", "ceo", "owner", "principal", "managing director", "president"],
    "ops": ["operations", "ops", "cto", "chief", "vp ", "head of", "director", "coo", "rev ops", "revops"],
    "ai": ["ai ", "artificial intelligence", "machine learning", "ml ", "llm", "genai", "generative"],
}

# Comments that carry no qualifying signal — dropped by the free pre-filter.
_GENERIC = {
    "great post", "love this", "well said", "so true", "thanks for sharing", "congrats",
    "congratulations", "amazing", "awesome", "nice", "agreed", "this", "facts", "100%",
    "great share", "spot on", "interesting", "wow", "🔥", "👏", "💯",
}
_EMOJI_ONLY = re.compile(r"^[\W_]+$", re.UNICODE)


def prefilter(comment_text: str | None) -> bool:
    """True = worth spending a /profile credit on. Free heuristic."""
    t = (comment_text or "").strip().lower()
    if len(t) < 12:                      # one-word / emoji reactions
        return False
    if _EMOJI_ONLY.match(t):
        return False
    if t in _GENERIC:
        return False
    # mostly-generic short blurbs ("great post, thanks!")
    words = re.findall(r"[a-z']+", t)
    if len(words) <= 4 and all(w in {w2 for g in _GENERIC for w2 in g.split()} for w in words):
        return False
    return True


def _keyword_score(headline: str) -> tuple[int, list[str]]:
    h = f" {headline.lower()} "
    hits = [grp for grp, kws in ICP_KEYWORDS.items() if any(k in h for k in kws)]
    # legal/agency/founder are strong buyer signals; ops/ai are supporting.
    strong = {"legal", "agency", "founder"}
    score = 0
    for g in hits:
        score += 35 if g in strong else 18
    return min(score, 100), hits


_SYS = (
    "You qualify LinkedIn leads for an AI-automation consultant whose buyers are: "
    "legal / legal-ops teams, AI agencies & consultancies, company founders/CEOs, "
    "and ops/CTO/automation decision-makers. Given a person's headline (and maybe "
    "an about blurb), decide if they fit that ICP. Reply ONLY compact JSON: "
    '{"fit": true|false, "score": 0-100, "reason": "<=12 words"}.'
)


def score_lead(headline: str | None, about: str | None = None) -> tuple[bool, int, str]:
    """Return (fit, score, reason). Keyword-first; LLM only for the borderline band."""
    headline = (headline or "").strip()
    if not headline:
        return (False, 0, "no headline")

    kw_score, hits = _keyword_score(headline)
    if kw_score >= 70:
        return (True, kw_score, f"keyword: {', '.join(hits)}")
    if kw_score == 0 and not about:
        return (False, 0, "no ICP keywords")

    # borderline → cheap LLM tiebreak
    try:
        raw = complete("lead_icp", _SYS, f"Headline: {headline}\nAbout: {(about or '')[:400]}")
        data = json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group(0))
        fit = bool(data.get("fit"))
        score = int(data.get("score", kw_score))
        return (fit, max(0, min(100, score)), str(data.get("reason", ""))[:120])
    except Exception as e:  # noqa: BLE001
        _log.error("icp_llm_failed", str(e), metadata={"headline": headline[:80]})
        # fall back to keyword verdict
        return (kw_score >= 50, kw_score, f"keyword-fallback: {', '.join(hits) or 'none'}")
