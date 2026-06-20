"""Track recent posts from each influencer + score for engagement.

Every 4h. Per platform:
  - LinkedIn: Unipile /api/v1/users/{provider_id}/posts (or fallback: scrape)
  - Twitter: enqueue Browser Use scrape job (Typefully has no read-others API)
  - Facebook: skipped here; group activity covers reach (groups/scanner.py)

For each new post: LLM scores relevance 0-100 against pillars; if >=60,
generate a you-voice suggested_comment. Insert into influencer_posts.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

from shared.logging.logger import AgentLogger

from ..repurposer import brand_voice
from ..repurposer.llm import complete
from . import store

_log = AgentLogger("influencer-tracker")


def _score_and_comment(body: str) -> tuple[int, str | None, str | None]:
    """LLM call: returns (score 0-100, suggested_action, suggested_comment).

    Cheap-ish: one Haiku call per post.
    """
    sys = (
        brand_voice.VOICE_DOC
        + "\n\nGiven a post by someone in our space, output JSON only: "
        '{"score": 0-100 (relevance to my Pillar 1 = AI for SMBs / Pillar 2 = '
        'consultant building in public), '
        '"action": "comment"|"repost_with_commentary"|"repurpose"|"tag"|"ignore", '
        '"comment": "<2-3 sentence comment in my voice that adds genuine value, '
        'never pitches; null if action=ignore">}. '
        "No prose, no markdown."
    )
    try:
        raw = complete("inbox_reply", sys, f"Post:\n{body[:1500]}")
    except Exception as e:
        _log.error("score_failed", str(e))
        return 0, None, None

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        d = json.loads(cleaned.strip())
        return int(d.get("score") or 0), d.get("action"), d.get("comment")
    except Exception as e:
        _log.error("parse_failed", str(e), metadata={"raw": cleaned[:120]})
        return 0, None, None


async def _track_linkedin(inf: dict[str, Any]) -> int:
    """Pull recent posts via Unipile (best-effort)."""
    api_key = os.getenv("UNIPILE_API_KEY")
    dsn = os.getenv("UNIPILE_DSN")
    account_id = os.getenv("UNIPILE_LINKEDIN_ACCOUNT_ID")
    if not (api_key and dsn and account_id):
        return 0

    headers = {"X-API-KEY": api_key}
    handle = inf["handle"]
    saved = 0
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.get(
                f"{dsn}/api/v1/users/{handle}/posts",
                headers=headers,
                params={"account_id": account_id, "limit": 5},
            )
            if r.status_code != 200:
                return 0
            for p in r.json().get("items", []):
                body = p.get("text") or p.get("body") or ""
                if not body:
                    continue
                score, action, comment = _score_and_comment(body)
                store.upsert_post(
                    influencer_id=inf["id"],
                    platform="linkedin",
                    external_id=p.get("id") or p.get("urn") or "",
                    posted_at=p.get("created_at"),
                    body=body,
                    post_url=p.get("url"),
                    likes=p.get("reactions_count"),
                    comments=p.get("comments_count"),
                    reposts=p.get("reposts_count"),
                    relevance_score=score,
                    suggested_action=action,
                    suggested_comment=comment,
                )
                saved += 1
        except Exception as e:
            _log.error("linkedin_track_failed", str(e),
                       metadata={"handle": handle})
    return saved


async def fetch_recent() -> None:
    """Cron entrypoint — runs every 4h. LinkedIn only."""
    li = store.list_tracked(platform="linkedin", limit=30)
    li_saved = 0
    for inf in li:
        try:
            li_saved += await _track_linkedin(inf)
        except Exception as e:
            _log.error("li_track_loop", str(e))
    _log.log("tracker_done", metadata={"linkedin_posts_saved": li_saved})


if __name__ == "__main__":
    asyncio.run(fetch_recent())
