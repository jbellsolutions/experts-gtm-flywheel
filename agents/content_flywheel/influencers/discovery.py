"""LLM cold-discovery — nominates 20 LinkedIn + 30 Twitter people in our space.

Runs daily 5am UTC. Uses your pillar definitions + brand voice as the seed.
Cross-references against existing rows so we don't re-nominate.

Per the v4 plan: seed with LLM cold-generation since you opted for that
over a manual starter list.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from shared.logging.logger import AgentLogger

from ..repurposer import brand_voice
from ..repurposer.llm import complete
from . import store

_log = AgentLogger("influencer-discovery")

TARGET_COUNTS = {"linkedin": 12}  # fits within idea_suggester 2000-token cap


def _system_prompt() -> str:
    return (
        brand_voice.VOICE_DOC
        + "\n\nYou are nominating LinkedIn influencers for me to engage with. "
        "Output STRICTLY JSON only, no prose, no markdown fences. "
        "Schema: {\"linkedin\":[{handle,full_name,headline,profile_url,pillars,why,score}]}. "
        "handle is the LinkedIn URL slug (e.g. 'janedoe', no @). "
        "pillars is a subset of [\"1\",\"2\"]: "
        "1=ask-me-anything (clients, objections, AI tactics for SMBs), "
        "2=certification journey + consultant building in public. "
        "score is 0-100 relevance to my work. "
        "ONLY nominate real, recognizable people active in AI automation, "
        "no-code/low-code, SMB consulting, agentic workflows, or solo-founder building. "
        "Profile URL must be a real LinkedIn URL pattern (linkedin.com/in/<slug>)."
    )


def _user_prompt(existing_handles: dict[str, set[str]]) -> str:
    skip_li = ", ".join(sorted(existing_handles.get("linkedin", set()))) or "(none)"
    return (
        f"Nominate {TARGET_COUNTS['linkedin']} LinkedIn people for me to track. "
        f"Skip these handles I already track: {skip_li}. "
        f"Mix: 60% Pillar 1 (operators, agency owners, AI tacticians for SMBs), "
        f"40% Pillar 2 (consultants building in public, certification journey). "
        f"Bias toward people who post frequently and engage with comments."
    )


def _existing_handles() -> dict[str, set[str]]:
    from shared.db import db
    rows = db().table("influencers").select("platform, handle").execute().data or []
    out: dict[str, set[str]] = {}
    for r in rows:
        out.setdefault(r["platform"], set()).add(r["handle"])
    return out


async def suggest_new() -> None:
    """Cron entrypoint — runs daily 5am UTC."""
    existing = _existing_handles()
    try:
        raw = complete("idea_suggester",  # reuse the suggester model spec (Sonnet)
                       _system_prompt(),
                       _user_prompt(existing))
    except Exception as e:
        _log.error("llm_failed", str(e))
        return

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        parsed = json.loads(cleaned.strip())
    except Exception as e:
        _log.error("parse_failed", str(e), metadata={"raw_preview": cleaned[:200]})
        return

    inserted = 0
    for platform in ("linkedin",):
        for cand in parsed.get(platform, []):
            handle = (cand.get("handle") or "").lstrip("@").strip()
            if not handle or handle in existing.get(platform, set()):
                continue
            url = cand.get("profile_url") or f"https://www.linkedin.com/in/{handle}"
            try:
                store.upsert_influencer(
                    platform=platform,
                    handle=handle,
                    profile_url=url,
                    full_name=cand.get("full_name"),
                    headline=cand.get("headline") or cand.get("bio"),
                    pillars=cand.get("pillars") or [],
                    relevance_score=int(cand.get("score") or 50),
                    discovered_via="llm_seed",
                    metadata={"why": cand.get("why")},
                )
                inserted += 1
            except Exception as e:
                _log.error("upsert_failed", str(e),
                           metadata={"handle": handle, "platform": platform})

    _log.log("discovery_done", metadata={"inserted": inserted})


if __name__ == "__main__":
    asyncio.run(suggest_new())
