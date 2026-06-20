"""Weekly KPI targets + week-to-date progress.

Targets reflect the strategy doc's Month 1-3 goals, scaled for the early
weeks. Edit `WEEKLY_TARGETS` to retune.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from shared.db import db


# Per-week targets — what "doing the job" looks like.
# Values are cumulative for the calendar week (Mon-Sun).
WEEKLY_TARGETS: dict[str, dict] = {
    "linkedin_posts_published":   {"target": 25, "label": "LinkedIn posts (5/day × 5)"},
    "substack_posts_published":   {"target":  1, "label": "Substack post (1/wk)"},
    "medium_articles_published":  {"target":  1, "label": "Medium article (1/wk)"},
    "newsletter_sent":            {"target":  1, "label": "Newsletter broadcast (1/wk)"},
    "lives_recorded":             {"target":  2, "label": "YouTube lives (Tue + Thu)"},
    "linkedin_comments_given":    {"target": 25, "label": "Quality LI comments out (5/day)"},
}


def _week_bounds(today: date) -> tuple[str, str]:
    """Return ISO start/end of the current Mon-Sun week."""
    monday = today - timedelta(days=today.weekday())
    sunday_next = monday + timedelta(days=7)
    return monday.isoformat(), sunday_next.isoformat()


def week_to_date(today: date) -> dict[str, dict]:
    """Compute current-week progress against each KPI. Returns:

    {
      "linkedin_posts_published": {"target": 25, "actual": 12, "label": "...", "pct": 48},
      ...
    }
    """
    week_start, week_end = _week_bounds(today)
    result: dict[str, dict] = {}

    # Helper to query drafts by platform/format with a status filter
    def _published(platform: str, fmt: str | None = None) -> int:
        q = db().table("drafts").select("id", count="exact").eq(
            "status", "published"
        ).eq("platform", platform).gte("published_at", week_start).lt(
            "published_at", week_end
        )
        if fmt:
            q = q.eq("format", fmt)
        try:
            return q.execute().count or 0
        except Exception:
            return 0

    counts = {
        "linkedin_posts_published":  _published("linkedin",  "post"),
        "substack_posts_published":  _published("substack",  "post"),
        "medium_articles_published": _published("medium",    "article"),
        "newsletter_sent":           _published("newsletter", "section"),
    }

    # Lives recorded = transcripts ingested this week
    try:
        live_count = db().table("transcripts").select("id", count="exact").gte(
            "ingested_at", week_start
        ).lt("ingested_at", week_end).execute().count or 0
    except Exception:
        live_count = 0
    counts["lives_recorded"] = live_count

    # Inbox + follow-ups retired — internal note
    # Manual KPIs (you self-report; we track via daily_checklist completion)
    # These will be 0 until we wire engagement-out items to a counter.
    counts["linkedin_comments_given"] = 0

    for kpi, spec in WEEKLY_TARGETS.items():
        actual = counts.get(kpi, 0)
        target = spec["target"]
        result[kpi] = {
            "target": target,
            "actual": actual,
            "label": spec["label"],
            "pct": min(100, int(round(100 * actual / target))) if target else 0,
        }
    return result
