"""Find LinkedIn posts to comment on — safely, via Firecrawl (no LinkedIn login).

Browser Use Cloud has no LinkedIn profile configured and you asked us never
to touch his LinkedIn account, so we discover comment targets the same safe way
we discover influencers: Firecrawl searches Google's index.

Approach:
  1. Build queries from (a) our tracked influencers by name and (b) AI keywords,
     all scoped to site:linkedin.com/posts/.
  2. For each hit, score the snippet + draft a comment in your voice via the
     shared `_score_and_comment` helper (one Haiku call).
  3. Keep score >= MIN_SCORE with a real comment; write into `influencer_posts`
     (our_engagement_status='none') so they surface on the Comments tab.
  4. Authors we didn't already track get added as influencers tagged
     discovered_via='comment_search' and parked status='snoozed' (Cold) so they
     don't flood the Tracked Kanban — you promotes the good ones.

Runs daily (see workflows/scheduler.py). Cost: ~25-30 Firecrawl credits + a
few cents of Haiku per run.
"""
from __future__ import annotations

import asyncio
import re

from shared.logging.logger import AgentLogger
from shared.db import db
from .discovery_firecrawl import _firecrawl_search, _name_from_title
from .tracker import _score_and_comment
from . import store as ist

_log = AgentLogger("comment-finder")

KEYWORD_QUERIES = [
    "site:linkedin.com/posts/ artificial intelligence agents",
    "site:linkedin.com/posts/ generative AI business",
    "site:linkedin.com/posts/ AI automation SMB",
    "site:linkedin.com/posts/ Claude Anthropic",
    "site:linkedin.com/posts/ AI consultant",
]
MIN_SCORE = 50
TARGET = 10            # 10 fresh comment targets per daily run (your cadence)
NAME_QUERIES = 15      # how many tracked influencers to search by name


async def find_targets(target: int = TARGET) -> None:
    """Cron entrypoint."""
    infs = (db().table("influencers").select("id,handle,full_name")
            .eq("platform", "linkedin").eq("status", "tracked")
            .limit(40).execute().data or [])
    by_handle = {i["handle"].lower(): i for i in infs}

    queries = [f'site:linkedin.com/posts/ "{(i.get("full_name") or i["handle"])}"'
               for i in infs[:NAME_QUERIES]]
    queries += KEYWORD_QUERIES

    inserted = 0
    new_authors: list[str] = []
    seen: set[str] = set()
    for q in queries:
        if inserted >= target:
            break
        for h in await _firecrawl_search(q, limit=6):
            u = h.get("url", "")
            if "linkedin.com/posts/" not in u:
                continue
            pid = u.split("?")[0]
            if pid in seen:
                continue
            seen.add(pid)
            snippet = (h.get("description") or h.get("title") or "")
            if len(snippet) < 20:
                continue
            score, action, comment = _score_and_comment(snippet)
            if score < MIN_SCORE or action == "ignore" or not comment:
                continue
            mm = re.search(r"/posts/([^_/?#]+)", u)
            slug = mm.group(1) if mm else None
            inf = by_handle.get((slug or "").lower())
            if not inf and slug:
                inf = ist.upsert_influencer(
                    platform="linkedin", handle=slug,
                    profile_url=f"https://www.linkedin.com/in/{slug}",
                    full_name=_name_from_title(h.get("title", "")),
                    relevance_score=score, discovered_via="comment_search",
                    metadata={"from": "post_search"})
                new_authors.append(inf["id"])
            if not inf:
                continue
            try:
                db().table("influencer_posts").upsert({
                    "influencer_id": inf["id"], "platform": "linkedin",
                    "external_id": pid, "post_url": pid, "body": snippet[:1500],
                    "relevance_score": score, "suggested_action": action,
                    "suggested_comment": comment, "our_engagement_status": "none",
                    "raw": {"title": h.get("title"), "q": q},
                }, on_conflict="platform,external_id").execute()
                inserted += 1
            except Exception as e:
                _log.error("post_upsert_failed", str(e))

    # Keep comment-search authors out of the Tracked board → Cold.
    if new_authors:
        db().table("influencers").update({"status": "snoozed"}).in_(
            "id", new_authors).execute()

    _log.log("comment_targets_found", metadata={
        "inserted": inserted, "new_authors": len(new_authors)})


if __name__ == "__main__":
    asyncio.run(find_targets())
