"""Find LinkedIn posts to comment on — safely, via ScrapeCreators (no LinkedIn login).

For each of our tracked influencers (the people we already follow + keep on the
Tracked board), we pull their recent posts through ScrapeCreators — the same
public-data collector the lead-gen pipeline uses, with **zero footprint on
your own LinkedIn account** — then keep only posts that are:

  * FRESH  — posted within FRESH_DAYS, and
  * have TRACTION — a real, confirmed comment count >= MIN_COMMENTS, and
  * NEW    — we haven't already stored / commented on / dismissed them.

For each survivor we draft a 2-3 sentence comment in your voice (one Haiku
call) and write it to `influencer_posts` (our_engagement_status='none') so it
surfaces on the Comments tab. Net: the daily feed is high-signal — posts from
people we follow, that actually have traction, that we haven't touched yet.

This REPLACES the old Firecrawl keyword search, which surfaced random posts with
no engagement data (no way to require >=50 comments).

Cost per run: 1 ScrapeCreators credit per influencer profile (<= MAX_INFLUENCERS)
+ 1 per post we confirm the comment count on (<= MAX_CONFIRMS). The Unipile
post-tracker stays OFF (it touched your account) — ScrapeCreators is the safe
substitute. Runs daily (workflows/content_pipeline.py).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from shared.db import db
from shared.logging.logger import AgentLogger
from .tracker import _score_and_comment
from . import store as ist
from ..leadgen import scrapecreators as sc

_log = AgentLogger("comment-finder")

MIN_SCORE = 50          # relevance bar (Haiku) to surface a post
MIN_COMMENTS = 50       # your bar: only high-traction posts (>= 50 comments)
TARGET = 10             # fresh qualifying targets per daily run
FRESH_DAYS = 14         # only posts from the last 2 weeks
MAX_INFLUENCERS = 25    # tracked influencers to scan (1 profile credit each)
PER_INFLUENCER = 3      # newest fresh posts to consider per influencer
MAX_CONFIRMS = 30       # cap post() comment-count confirmations (1 credit each)


def _posted_within(posted_at, days: int) -> bool:
    """True if `posted_at` (ISO string) is within the last `days`. Missing/unparseable
    dates are treated as too-old (we only want demonstrably fresh posts)."""
    if not posted_at:
        return False
    try:
        dt = datetime.fromisoformat(str(posted_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt >= datetime.now(timezone.utc) - timedelta(days=days)


def _existing_external_ids() -> set[str]:
    """LinkedIn post URLs we've already DRAFTED A COMMENT FOR (or engaged / dismissed)
    — the cross-run dedup set so we never re-surface a post we've already handled.

    We deliberately do NOT dedup on bare row-existence: the lead-gen pipeline also
    writes rows to `influencer_posts` (it scrapes commenters off target posts) with
    NO suggested_comment and NO relevance_score. Deduping on existence let those
    score-less rows "claim" a post so comment_finder skipped it forever — starving
    the Comments tab (which requires relevance_score >= 50). Now those rows stay
    eligible: comment_finder drafts a comment and upserts (on_conflict
    platform,external_id) which fills in the score + comment in place."""
    rows = (db().table("influencer_posts")
            .select("external_id,suggested_comment,our_engagement_status")
            .eq("platform", "linkedin").execute().data or [])
    done: set[str] = set()
    for r in rows:
        eid = r.get("external_id")
        if not eid:
            continue
        engaged = (r.get("our_engagement_status") or "none") != "none"
        if r.get("suggested_comment") or engaged:
            done.add(eid)
    return done


async def find_targets(target: int = TARGET) -> None:
    """Cron entrypoint — surface up to `target` fresh, >=MIN_COMMENTS posts from our
    tracked influencers, each with a drafted comment. No-op if ScrapeCreators is
    unconfigured (we need real comment counts; there's no safe free substitute)."""
    if not sc.configured():
        _log.log("comment_finder_skipped", metadata={"reason": "SCRAPECREATORS_API_KEY unset"})
        return

    infs = ist.list_tracked(platform="linkedin", limit=MAX_INFLUENCERS)
    if not infs:
        _log.log("comment_finder_no_influencers")
        return

    have = _existing_external_ids()

    # 1. Gather fresh, not-yet-stored candidate posts (profile = 1 credit each).
    #    recent_posts() comes back newest-first; keep up to PER_INFLUENCER per person.
    candidates: list[dict] = []
    profiles = 0
    for inf in infs:
        url = inf.get("profile_url") or inf.get("handle")
        if not url:
            continue
        try:
            prof = sc.profile(url)
            profiles += 1
        except Exception as e:
            _log.error("profile_failed", str(e), metadata={"handle": inf.get("handle")})
            continue
        kept = 0
        for p in sc.recent_posts(prof):
            if kept >= PER_INFLUENCER:
                break
            pid = (p.get("url") or "").split("?")[0]
            if not pid or pid in have:
                continue
            if not _posted_within(p.get("posted_at"), FRESH_DAYS):
                continue
            have.add(pid)  # avoid re-considering within this run
            candidates.append({
                "url": pid, "body": p.get("body") or "",
                "posted_at": p.get("posted_at"),
                "cc_hint": p.get("comment_count"), "inf": inf,
            })
            kept += 1

    # Freshest first → spend our confirm budget on the most timely posts.
    candidates.sort(key=lambda c: str(c["posted_at"] or ""), reverse=True)

    # 2. Confirm the real comment count (post = 1 credit), keep >= MIN_COMMENTS,
    #    draft a comment, insert — until we hit `target` or the confirm cap.
    inserted = confirms = 0
    for c in candidates:
        if inserted >= target or confirms >= MAX_CONFIRMS:
            break
        cc, body = c["cc_hint"], c["body"]
        if cc is None or len(body) < 20:          # profile rarely carries either → confirm
            try:
                pj = sc.post(c["url"])
                confirms += 1
            except Exception as e:
                _log.error("post_failed", str(e), metadata={"url": c["url"]})
                continue
            meta = sc.post_meta(pj)
            cc = meta.get("comment_count") or 0
            body = body or meta.get("body") or ""
        if (cc or 0) < MIN_COMMENTS or len(body) < 20:
            continue
        score, action, comment = _score_and_comment(body)
        if score < MIN_SCORE or action == "ignore" or not comment:
            continue
        try:
            ist.upsert_post(
                influencer_id=c["inf"]["id"], platform="linkedin",
                external_id=c["url"], post_url=c["url"], posted_at=c["posted_at"],
                body=body[:1500], comments=cc, relevance_score=score,
                suggested_action=action, suggested_comment=comment,
                raw={"src": "scrapecreators", "comment_count": cc})
            inserted += 1
        except Exception as e:
            _log.error("post_upsert_failed", str(e))

    # 3. Enrich high-traction posts ALREADY in the table that don't have a drafted
    #    comment yet — chiefly the ones the lead-gen pipeline scraped (it stores the
    #    target post + its real comment count but never drafts a comment). Without
    #    this the Comments tab ignores those posts entirely even though they're the
    #    freshest, highest-traction AI posts we've seen. Draft a comment in place.
    enriched = 0
    if inserted < target:
        since = (datetime.now(timezone.utc) - timedelta(days=FRESH_DAYS)).isoformat()
        try:
            rows = (db().table("influencer_posts")
                    .select("id,body,comments")
                    .eq("platform", "linkedin").gte("comments", MIN_COMMENTS)
                    .gte("posted_at", since).is_("suggested_comment", "null")
                    .eq("our_engagement_status", "none")
                    .order("comments", desc=True).limit(target * 4).execute().data or [])
        except Exception as e:  # noqa: BLE001
            _log.error("enrich_query_failed", str(e))
            rows = []
        for r in rows:
            if inserted >= target:
                break
            body = r.get("body") or ""
            if len(body) < 20:
                continue
            score, action, comment = _score_and_comment(body)
            if score < MIN_SCORE or action == "ignore" or not comment:
                continue
            try:
                db().table("influencer_posts").update({
                    "relevance_score": score, "suggested_action": action,
                    "suggested_comment": comment,
                }).eq("id", r["id"]).execute()
                inserted += 1
                enriched += 1
            except Exception as e:  # noqa: BLE001
                _log.error("enrich_update_failed", str(e))

    _log.log("comment_targets_found", metadata={
        "inserted": inserted, "enriched": enriched, "candidates": len(candidates),
        "profiles": profiles, "confirms": confirms,
        "capped": confirms >= MAX_CONFIRMS and inserted < target})


if __name__ == "__main__":
    asyncio.run(find_targets())
