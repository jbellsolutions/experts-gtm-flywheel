"""AI lead qualification — one cheap pass over each newly-scraped commenter.

A good lead is a DECISION-MAKER at a small (~1-50) company who is either a
potential BUYER interested in AI / the post's topic (ai_prospect) or someone who
SELLS or BUILDS AI products/services (ai_provider). Company size is inferred from
the headline here; the strict 1-50 gate is confirmed later at enrichment (which
returns real headcount). Haiku, tiny JSON — no paid enrichment, runs first.
"""
from __future__ import annotations

import json

from shared.logging.logger import AgentLogger

from ..repurposer.llm import complete

_log = AgentLogger("leadgen.qualify")

_SYSTEM = (
    "You qualify inbound B2B leads: people who publicly engaged with a LinkedIn post about "
    "AI / using AI to grow a business. For the person below, decide:\n"
    "1. decision_maker — true if their role implies authority to buy for a business (founder, "
    "owner, co-founder, CEO/CxO, president, partner, VP, Head of, Director, or they run their "
    "own practice/agency/firm). Individual contributors, students, job-seekers and interns are "
    "false.\n"
    "2. lead_type — 'ai_provider' if they SELL or BUILD AI products/services (AI agency, AI "
    "consultant, automation studio, AI SaaS founder, etc.); 'ai_prospect' if they're a "
    "potential BUYER — a business person interested in AI / the topic but not primarily an AI "
    "vendor; 'neither' if there is no AI relevance at all.\n"
    "3. company_size_hint — 'small' (~1-50: founder/owner of a small firm, solo, boutique "
    "agency), 'large' (clearly enterprise or big-company employee), or 'unknown'.\n"
    "4. qualified — true ONLY if decision_maker is true AND lead_type is not 'neither' AND "
    "company_size_hint is not 'large'.\n"
    "5. reason — <=12 words, plain English.\n\n"
    'Return STRICT JSON only (no markdown): {"decision_maker":true|false,'
    '"lead_type":"ai_provider|ai_prospect|neither","company_size_hint":"small|large|unknown",'
    '"qualified":true|false,"reason":"..."}'
)


def _user(lead: dict) -> str:
    return (
        f"NAME: {lead.get('name') or '(unknown)'}\n"
        f"LINKEDIN HEADLINE / ROLE: {lead.get('headline') or '(unknown)'}\n"
        f"WHAT THEY SAID on the post: {lead.get('comment_text') or '(nothing captured)'}\n"
        f"POST THEY ENGAGED WITH: {lead.get('post_url') or '(unknown)'}"
    )


def _parse(raw: str) -> dict | None:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = s.split("```")[1]
        if s.startswith("json"):
            s = s[4:]
    try:
        d = json.loads(s.strip())
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(d, dict):
        return None
    lt = str(d.get("lead_type", "neither")).strip().lower()
    if lt not in ("ai_provider", "ai_prospect", "neither"):
        lt = "neither"
    size = str(d.get("company_size_hint", "unknown")).strip().lower()
    if size not in ("small", "large", "unknown"):
        size = "unknown"
    dm = bool(d.get("decision_maker"))
    # Re-derive qualified from the rule (don't blindly trust the model's bool).
    qualified = dm and lt != "neither" and size != "large"
    return {"decision_maker": dm, "lead_type": lt, "company_size_hint": size,
            "qualified": qualified, "reason": str(d.get("reason", "")).strip()[:120]}


def qualify_lead(lead: dict) -> dict | None:
    """Return {decision_maker, lead_type, company_size_hint, qualified, reason} or None.

    `lead` keys used: name, headline, comment_text, post_url.
    """
    try:
        raw = complete("lead_qualify", _SYSTEM, _user(lead))
    except Exception as e:  # noqa: BLE001
        _log.error("qualify_failed", str(e), metadata={"lead": (lead.get("name") or "")[:60]})
        return None
    return _parse(raw)
