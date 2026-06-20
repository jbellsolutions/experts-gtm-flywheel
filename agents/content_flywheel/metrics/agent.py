"""Weekly engagement metrics fetcher.

Pulls stats for every published draft from the last 30 days, snapshots into
post_metrics. Friday cron drives this; the weekly_digest then summarizes.

Per-platform:
  - linkedin  → Unipile post stats endpoint
  - substack  → manual or future browser scrape
  - medium    → manual or future browser scrape
  - newsletter → Kit broadcast stats endpoint (TODO)
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from shared.db import db
from shared.logging.logger import AgentLogger

_log = AgentLogger("metrics_fetcher")
_HORIZON_DAYS = 30


# ── LinkedIn (via Unipile) ─────────────────────────────────────────────

async def _linkedin_stats(publish_url: str) -> dict[str, Any] | None:
    api_key = os.getenv("UNIPILE_API_KEY")
    dsn = os.getenv("UNIPILE_DSN")
    if not (api_key and dsn):
        return None
    # Extract post URN from URL: https://www.linkedin.com/feed/update/urn:li:activity:1234/
    m = re.search(r"(urn:li:[a-zA-Z]+:\d+)", publish_url)
    if not m:
        return None
    urn = m.group(1)
    headers = {"X-API-KEY": api_key, "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            r = await client.get(
                f"https://{dsn}/api/v1/linkedin/posts/{urn}",
                headers=headers,
            )
            r.raise_for_status()
            data = r.json() or {}
        except Exception as e:
            _log.error("linkedin_fetch_failed", str(e), metadata={"urn": urn})
            return None
    return {
        "likes":       data.get("reaction_counter") or data.get("likes"),
        "comments":    data.get("comment_counter") or data.get("comments"),
        "reposts":     data.get("repost_counter") or data.get("reposts"),
        "impressions": data.get("impressions"),
        "raw":         data,
    }


# ── Snapshot writer ────────────────────────────────────────────────────

def _snapshot(draft: dict, stats: dict[str, Any]) -> None:
    likes = stats.get("likes") or 0
    comments = stats.get("comments") or 0
    reposts = stats.get("reposts") or 0
    engagement = (likes or 0) + (comments or 0) + (reposts or 0)
    db().table("post_metrics").insert({
        "draft_id":     draft["id"],
        "platform":     draft["platform"],
        "publish_url":  draft.get("publish_url"),
        "impressions": stats.get("impressions"),
        "likes":       likes or None,
        "comments":    comments or None,
        "reposts":     reposts or None,
        "clicks":      stats.get("clicks"),
        "engagement":  engagement or None,
        "raw":         stats.get("raw") or {},
    }).execute()


# ── Public entrypoint ──────────────────────────────────────────────────

FETCHERS = {
    "linkedin": _linkedin_stats,
}


async def fetch_all() -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_HORIZON_DAYS)).isoformat()
    drafts = (
        db().table("drafts").select("id, platform, publish_url, published_at")
        .eq("status", "published")
        .gte("published_at", cutoff)
        .not_.is_("publish_url", "null")
        .execute().data or []
    )
    _log.log("fetch_start", metadata={"candidates": len(drafts)})

    snapshots = 0
    for d in drafts:
        fetcher = FETCHERS.get(d["platform"])
        if not fetcher:
            continue
        try:
            stats = await fetcher(d["publish_url"])
        except Exception as e:
            _log.error("fetcher_crashed", str(e),
                       metadata={"platform": d["platform"], "draft_id": d["id"]})
            continue
        if stats:
            _snapshot(d, stats)
            snapshots += 1

    _log.log("fetch_done", metadata={"snapshots_written": snapshots})


if __name__ == "__main__":
    asyncio.run(fetch_all())
