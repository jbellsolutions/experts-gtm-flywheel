"""Suggest 1-3 influencer handles to tag in a draft body.

Used by the dashboard "+ suggest tags" button on DraftCard, and called
inline by the repurposer at generation time for longer LinkedIn drafts.

Heuristic, not LLM (cheap):
  - Match draft pillar against influencer.pillars
  - Prefer influencers with last_engaged_at > 30 days ago (or null) so we
    don't keep tagging the same person
  - Sort by relevance_score desc
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from shared.db import db


def suggest(
    *,
    pillar: str,
    platform: str,
    limit: int = 3,
    cooldown_days: int = 30,
) -> list[dict[str, Any]]:
    """Return up to `limit` influencers worth tagging in a draft of this pillar."""
    q = (
        db().table("influencers")
        .select("id, handle, full_name, profile_url, pillars, relevance_score, last_engaged_at")
        .eq("status", "tracked")
        .eq("platform", platform)
        .contains("pillars", [pillar])
        .order("relevance_score", desc=True)
        .limit(limit * 3)  # over-fetch; filter cooldown in Python
    )
    rows = q.execute().data or []

    cutoff = (datetime.now(timezone.utc) - timedelta(days=cooldown_days)).isoformat()
    fresh = [
        r for r in rows
        if not r.get("last_engaged_at") or r["last_engaged_at"] < cutoff
    ]
    return fresh[:limit]


def mark_tagged(influencer_id: str) -> None:
    """Bump last_engaged_at when you actually used the suggestion."""
    db().table("influencers").update({
        "last_engaged_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", influencer_id).execute()
