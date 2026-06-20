"""Supabase wrappers for lead_contacts + leadgen_jobs (see migration 008)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from shared.db import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── lead_contacts ─────────────────────────────────────────────────────────────

def upsert_lead(
    *,
    profile_url: str,
    full_name: str | None = None,
    comment_text: str | None = None,
    headline: str | None = None,
    source_influencer_id: str | None = None,
    source_post_url: str | None = None,
    raw: dict | None = None,
) -> dict[str, Any]:
    """Idempotent on profile_url (= dedupe). Cheap first-touch insert; the
    commenter's headline (if the scraper gave one) shows in the Leads tab before
    enrichment. ICP + contact fields are filled in by the manual Enrich step."""
    row = {
        "profile_url": profile_url,
        "full_name": full_name,
        "comment_text": comment_text,
        "headline": headline,
        "source_influencer_id": source_influencer_id,
        "source_post_url": source_post_url,
        "raw": raw or {},
        "updated_at": _now(),
    }
    res = db().table("lead_contacts").upsert(row, on_conflict="profile_url",
                                             ignore_duplicates=False).execute()
    return (res.data or [row])[0]


def set_prefilter(lead_id: str, passed: bool) -> None:
    db().table("lead_contacts").update(
        {"prefilter_pass": passed, "updated_at": _now()}).eq("id", lead_id).execute()


def set_icp(lead_id: str, *, headline: str | None, about: str | None,
            fit: bool, score: int, reason: str) -> None:
    db().table("lead_contacts").update({
        "headline": headline, "about": about,
        "icp_fit": fit, "icp_score": score, "icp_reason": reason,
        "updated_at": _now(),
    }).eq("id", lead_id).execute()


def mark_enriched(lead_id: str, *, email: str | None, phone: str | None,
                  status: str = "enriched", headline: str | None = None,
                  about: str | None = None) -> None:
    upd: dict[str, Any] = {
        "email": email, "phone": phone,
        "enrichment_status": status, "enriched_at": _now(), "updated_at": _now(),
    }
    if headline:
        upd["headline"] = headline
    if about:
        upd["about"] = about
    db().table("lead_contacts").update(upd).eq("id", lead_id).execute()


def set_email_draft(lead_id: str, *, subject: str | None, body: str | None,
                    status: str = "drafted") -> None:
    db().table("lead_contacts").update({
        "draft_subject": subject, "draft_email": body,
        "email_status": status, "updated_at": _now(),
    }).eq("id", lead_id).execute()


# ── app_settings (editable offer framework lives here) ────────────────────────

def get_setting(key: str, default: str = "") -> str:
    row = (db().table("app_settings").select("value").eq("key", key)
           .limit(1).execute().data or [])
    return (row[0].get("value") if row else None) or default


def set_setting(key: str, value: str) -> None:
    db().table("app_settings").upsert(
        {"key": key, "value": value, "updated_at": _now()}, on_conflict="key").execute()


def existing_urls(urls: list[str]) -> set[str]:
    """Which of these profile_urls we already have (dedupe across batches)."""
    if not urls:
        return set()
    rows = (db().table("lead_contacts").select("profile_url")
            .in_("profile_url", urls).execute().data or [])
    return {r["profile_url"] for r in rows}


# ── leadgen_jobs ──────────────────────────────────────────────────────────────

def claim_next_job() -> dict[str, Any] | None:
    """Pop the oldest queued job and flip it to running (best-effort lock)."""
    rows = (db().table("leadgen_jobs").select("*").eq("status", "queued")
            .order("created_at").limit(1).execute().data or [])
    if not rows:
        return None
    job = rows[0]
    db().table("leadgen_jobs").update(
        {"status": "running", "started_at": _now()}).eq("id", job["id"]).execute()
    return job


def finish_job(job_id: str, *, status: str, stats: dict | None = None,
               error: str | None = None) -> None:
    db().table("leadgen_jobs").update({
        "status": status, "stats": stats or {}, "error": error,
        "finished_at": _now(),
    }).eq("id", job_id).execute()


def influencers_by_ids(ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    return (db().table("influencers").select("id, handle, profile_url, full_name")
            .in_("id", ids).execute().data or [])


def queued_for_enrich(limit: int = 25) -> list[dict[str, Any]]:
    """Leads the dashboard flagged for manual enrichment (per-row Enrich button).
    Returns everything the worker needs to enrich AND draft the offer email — the
    chosen voice + offer ride in `raw` (set by the dashboard at click time)."""
    return (db().table("lead_contacts")
            .select("id, profile_url, full_name, comment_text, raw")
            .eq("enrichment_status", "queued").limit(limit).execute().data or [])


# Offer frameworks are keyed offer_framework:<slug> (one per offer). The AI
# Integraterz slug falls back to the legacy single 'offer_framework' key so
# existing copy keeps working without a data migration.
def offer_framework(slug: str) -> str:
    val = get_setting(f"offer_framework:{slug}")
    if not val and slug == "ai_integraterz":
        val = get_setting("offer_framework")
    return val
