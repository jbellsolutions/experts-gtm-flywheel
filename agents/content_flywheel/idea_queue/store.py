"""Thin wrapper around the content_ideas + kv_state tables."""
from __future__ import annotations

from typing import Any

from shared.db import db


# ---------- content_ideas ----------

def insert_idea(
    *,
    source: str,
    content: str,
    priority: int = 50,
    parsed_content: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "source": source,
        "content": content,
        "priority": priority,
        "parsed_content": parsed_content or {},
        "metadata": metadata or {},
    }
    res = db().table("content_ideas").insert(row).execute()
    return (res.data or [row])[0]


def pending_ideas(limit: int = 10) -> list[dict[str, Any]]:
    res = (
        db().table("content_ideas")
        .select("*")
        .eq("status", "pending")
        .order("priority", desc=True)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def count_pending() -> int:
    res = (
        db().table("content_ideas")
        .select("id", count="exact")
        .eq("status", "pending")
        .execute()
    )
    return res.count or 0


def mark_used(idea_id: str, transcript_id: str | None = None) -> None:
    db().table("content_ideas").update({
        "status": "used",
        "used_at": "now()",
        "used_in_transcript_id": transcript_id,
    }).eq("id", idea_id).execute()


def boost(idea_id: str, delta: int = 10) -> None:
    cur = db().table("content_ideas").select("priority").eq("id", idea_id).single().execute().data
    new = max(0, min(100, (cur.get("priority", 50) if cur else 50) + delta))
    db().table("content_ideas").update({"priority": new}).eq("id", idea_id).execute()


def dismiss(idea_id: str) -> None:
    db().table("content_ideas").update({"status": "dismissed"}).eq("id", idea_id).execute()


def request_use_now(idea_id: str) -> None:
    """Flag an idea for immediate repurposing.

    Sets metadata.use_now_requested_at; the every-2-min `use_now_pending`
    cron picks these up and fires repurpose for them ASAP (without waiting
    for the off-cycle 21:00 UTC schedule).
    """
    from datetime import datetime, timezone
    cur = db().table("content_ideas").select("metadata").eq("id", idea_id).single().execute().data
    md = (cur or {}).get("metadata") or {}
    md["use_now_requested_at"] = datetime.now(timezone.utc).isoformat()
    db().table("content_ideas").update({
        "priority": 100,
        "metadata": md,
    }).eq("id", idea_id).execute()


def use_now_pending(limit: int = 5) -> list[dict[str, Any]]:
    """Return ideas that have a use_now_requested_at set and are still pending."""
    res = (
        db().table("content_ideas")
        .select("*")
        .eq("status", "pending")
        .not_.is_("metadata->>use_now_requested_at", "null")
        .order("priority", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


# ---------- kv_state ----------

def kv_get(key: str, default: Any = None) -> Any:
    res = db().table("kv_state").select("value").eq("key", key).execute()
    rows = res.data or []
    return rows[0]["value"] if rows else default


def kv_set(key: str, value: Any) -> None:
    db().table("kv_state").upsert({"key": key, "value": value, "updated_at": "now()"}).execute()
