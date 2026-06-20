"""Firecrawl-based safe influencer discovery.

Approach (zero LinkedIn touch from your account):
  1. Firecrawl /v1/search queries Google's index for AI / Anthropic / Claude
     LinkedIn profiles. Returns {url, title, description} per hit.
  2. Sonnet reads each result and judges:
       - relevance to your pillars (0-100)
       - authority signal from title/description (employer, role, etc.)
       - "Worth tracking?" boolean
  3. Top-scored real LinkedIn profile candidates land in `influencers`
     with discovered_via='firecrawl_search'.

LinkedIn's anti-bot now login-walls anonymous profile views, so we can't
auto-verify >5k followers / >20-comment thresholds. Instead the LLM uses
title/description heuristics (e.g. 'Head of Claude Code at Anthropic' is a
clearer authority signal than any follower count). you review the
daily 5 in his Slack brief — dismissing duds is the threshold filter.

Runs daily 5am UTC. Costs:
  - Firecrawl: 1 credit per search query × 6 queries = 6 credits/day
    (~180/month, well inside the 5000-credit plan)
  - Sonnet scoring: one call for the whole batch, ~$0.05/day
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from shared.logging.logger import AgentLogger
from ..repurposer import brand_voice
from ..repurposer.llm import complete
from . import store

_log = AgentLogger("influencer-discovery-firecrawl")

FIRECRAWL_URL = "https://api.firecrawl.dev/v1/search"

# Rotating queries — each one targets a different slice of the AI / Anthropic
# / Claude / agent-builder space. We cycle through these so we don't keep
# returning the same top-10 every day.
QUERIES = [
    "site:linkedin.com/in/ Anthropic Claude Member of Technical Staff",
    "site:linkedin.com/in/ AI agent builder operator founder",
    "site:linkedin.com/in/ artificial intelligence consultant SMB",
    "site:linkedin.com/in/ Claude code engineer developer Anthropic",
    "site:linkedin.com/in/ AI automation agency owner",
    "site:linkedin.com/in/ no-code AI workflows founder",
]

PER_QUERY_LIMIT = 8     # Firecrawl results per query
KEEP_TOP_N = 12         # how many candidates we LLM-score per day
INSERT_THRESHOLD = 60   # min Sonnet score to insert


def _slug_from_url(url: str) -> str | None:
    """Pull the public_identifier from a LinkedIn profile URL."""
    m = re.search(r"linkedin\.com/in/([^/?#]+)", url)
    return m.group(1).rstrip("/") if m else None


async def _firecrawl_search(query: str, limit: int = 8) -> list[dict[str, str]]:
    """Hit Firecrawl /v1/search. Returns list of {url, title, description}."""
    key = os.getenv("FIRECRAWL_API_KEY")
    if not key:
        _log.error("no_firecrawl_key", "FIRECRAWL_API_KEY not set")
        return []
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(
                FIRECRAWL_URL,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={"query": query, "limit": limit},
            )
            r.raise_for_status()
            j = r.json()
            return j.get("data") or []
        except Exception as e:
            _log.error("firecrawl_failed", str(e), metadata={"query": query[:60]})
            return []


def _score_prompt(candidates: list[dict]) -> tuple[str, str]:
    """Build the Sonnet system+user prompt that scores all candidates at once."""
    system = (
        brand_voice.VOICE_DOC
        + "\n\nYou are screening LinkedIn profile candidates that came back from "
        "a search for AI / Anthropic / Claude / agent-builder people. For each, "
        "output a relevance score 0-100 plus a one-line WHY. Output STRICTLY "
        "JSON only, no prose, no markdown fences.\n\n"
        "Schema: {\"results\":[{\"handle\":\"<linkedin slug>\","
        "\"score\":0-100,\"pillars\":[\"1\"|\"2\"],"
        "\"why\":\"<one line — what makes them worth engaging with>\","
        "\"keep\":true|false}]}\n\n"
        "Scoring rules:\n"
        "- Score ≥80: clearly authoritative (e.g. 'Head of X at Anthropic', "
        "'Founder of [recognized AI company]', 'Member of Technical Staff at "
        "Anthropic', 'CEO at [established AI agency]')\n"
        "- Score 60-79: solid signal (Founder/CEO of an AI-focused company, "
        "respected AI builder, recognized AI consultant with specific niche)\n"
        "- Score 40-59: maybe worth tracking but not obvious authority "
        "(generic 'AI Consultant' titles, unclear company)\n"
        "- Score <40: low signal or unrelated\n\n"
        "keep=true ONLY if score >= 60 AND the role/description suggests this "
        "person actually posts on LinkedIn about AI/Anthropic/Claude topics. "
        "Pillar 1 = AI tactics for SMBs / operator content. "
        "Pillar 2 = consultant-building-in-public / journey content."
    )
    listing = []
    for i, c in enumerate(candidates):
        handle = _slug_from_url(c.get("url", "")) or "?"
        listing.append(
            f"{i+1}. handle: {handle}\n"
            f"   url: {c.get('url','')}\n"
            f"   title: {(c.get('title') or '').strip()}\n"
            f"   description: {(c.get('description') or '').strip()[:240]}"
        )
    user = "Score these candidates:\n\n" + "\n\n".join(listing)
    return system, user


def _parse_score_output(raw: str) -> list[dict]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        parsed = json.loads(cleaned.strip())
        return parsed.get("results", []) if isinstance(parsed, dict) else []
    except Exception as e:
        _log.error("score_parse_failed", str(e),
                   metadata={"raw_preview": cleaned[:200]})
        return []


async def discover_real() -> None:
    """Cron entrypoint — runs daily 5am UTC."""
    _log.log("discover_start")
    existing = _existing_handles()

    # 1. Fan out search queries
    all_hits: dict[str, dict] = {}  # handle -> hit (dedupe by handle)
    for q in QUERIES:
        hits = await _firecrawl_search(q, limit=PER_QUERY_LIMIT)
        for h in hits:
            handle = _slug_from_url(h.get("url", ""))
            if not handle or handle in existing or handle in all_hits:
                continue
            all_hits[handle] = h

    if not all_hits:
        _log.log("no_candidates")
        return

    # 2. LLM scoring batch
    candidates = list(all_hits.values())[:KEEP_TOP_N * 2]  # over-fetch for headroom
    sys, usr = _score_prompt(candidates)
    try:
        raw = complete("idea_suggester", sys, usr)
    except Exception as e:
        _log.error("llm_failed", str(e))
        return
    scored = _parse_score_output(raw)

    # 3. Insert keepers
    inserted = 0
    skipped_below_threshold = 0
    for entry in scored:
        if not entry.get("keep"):
            continue
        score = int(entry.get("score") or 0)
        if score < INSERT_THRESHOLD:
            skipped_below_threshold += 1
            continue
        handle = (entry.get("handle") or "").lstrip("@").strip()
        if not handle or handle in existing:
            continue
        # Find the original Firecrawl hit
        src = all_hits.get(handle)
        if not src:
            continue
        try:
            store.upsert_influencer(
                platform="linkedin",
                handle=handle,
                profile_url=src.get("url") or f"https://www.linkedin.com/in/{handle}",
                full_name=_name_from_title(src.get("title", "")),
                headline=(src.get("description") or "").strip()[:280],
                pillars=entry.get("pillars") or [],
                relevance_score=score,
                discovered_via="firecrawl_search",
                metadata={
                    "why": entry.get("why"),
                    "search_title": src.get("title"),
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            inserted += 1
        except Exception as e:
            _log.error("upsert_failed", str(e), metadata={"handle": handle})

    _log.log("discover_done", metadata={
        "candidates": len(candidates),
        "scored": len(scored),
        "inserted": inserted,
        "below_threshold": skipped_below_threshold,
    })


def _name_from_title(title: str) -> str | None:
    """LinkedIn search titles look like 'Felix Rieseberg - Claude Cowork & Code...'.
    First chunk before ' - ' is usually the display name."""
    if not title:
        return None
    parts = re.split(r"\s+-\s+", title, maxsplit=1)
    return parts[0].strip() if parts else None


def _existing_handles() -> set[str]:
    from shared.db import db
    rows = db().table("influencers").select("handle").eq("platform", "linkedin").execute().data or []
    return {r["handle"] for r in rows}


if __name__ == "__main__":
    asyncio.run(discover_real())
