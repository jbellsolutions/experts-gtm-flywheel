"""Thin Supabase wrappers for influencers + influencer_posts."""
from __future__ import annotations

from typing import Any

from shared.db import db


def upsert_influencer(
    *,
    platform: str,
    handle: str,
    profile_url: str,
    full_name: str | None = None,
    headline: str | None = None,
    pillars: list[str] | None = None,
    relevance_score: int = 50,
    discovered_via: str = "manual",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Idempotent on (platform, handle). Returns the row."""
    row = {
        "platform": platform,
        "handle": handle,
        "profile_url": profile_url,
        "full_name": full_name,
        "headline": headline,
        "pillars": pillars or [],
        "relevance_score": max(0, min(100, relevance_score)),
        "discovered_via": discovered_via,
        "metadata": metadata or {},
    }
    res = db().table("influencers").upsert(
        row, on_conflict="platform,handle"
    ).execute()
    return (res.data or [row])[0]


def list_tracked(platform: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    q = db().table("influencers").select("*").eq("status", "tracked")
    if platform:
        q = q.eq("platform", platform)
    return (q.order("relevance_score", desc=True).limit(limit).execute().data) or []


def count_tracked() -> int:
    return db().table("influencers").select(
        "id", count="exact"
    ).eq("status", "tracked").execute().count or 0


def update_status(influencer_id: str, status: str) -> None:
    db().table("influencers").update({"status": status}).eq("id", influencer_id).execute()


def boost(influencer_id: str, delta: int = 10) -> None:
    cur = db().table("influencers").select("relevance_score").eq(
        "id", influencer_id
    ).single().execute().data
    new = max(0, min(100, (cur.get("relevance_score", 50) if cur else 50) + delta))
    db().table("influencers").update(
        {"relevance_score": new}
    ).eq("id", influencer_id).execute()


def upsert_post(
    *,
    influencer_id: str,
    platform: str,
    external_id: str,
    posted_at: str | None,
    body: str,
    post_url: str | None,
    likes: int | None = None,
    comments: int | None = None,
    reposts: int | None = None,
    relevance_score: int | None = None,
    suggested_action: str | None = None,
    suggested_comment: str | None = None,
    raw: dict | None = None,
) -> dict[str, Any]:
    row = {
        "influencer_id": influencer_id,
        "platform": platform,
        "external_id": external_id,
        "posted_at": posted_at,
        "body": body,
        "post_url": post_url,
        "likes": likes,
        "comments": comments,
        "reposts": reposts,
        "relevance_score": relevance_score,
        "suggested_action": suggested_action,
        "suggested_comment": suggested_comment,
        "raw": raw or {},
    }
    res = db().table("influencer_posts").upsert(
        row, on_conflict="platform,external_id"
    ).execute()
    return (res.data or [row])[0]


def todays_engage_list(platform: str, limit: int) -> list[dict[str, Any]]:
    """Top relevance, not-yet-engaged posts for the daily brief."""
    res = (
        db().table("influencer_posts")
        .select("*, influencers(handle, full_name, profile_url)")
        .eq("platform", platform)
        .eq("our_engagement_status", "none")
        .gte("relevance_score", 60)
        .order("relevance_score", desc=True)
        .order("posted_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def mark_post_engaged(post_id: str, action: str) -> None:
    db().table("influencer_posts").update({
        "our_engagement_status": action,
    }).eq("id", post_id).execute()
