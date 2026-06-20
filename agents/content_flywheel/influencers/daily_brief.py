"""Morning brief — surface today's 5 LinkedIn people to engage with.

Runs daily 6am UTC. Reads from the `influencers` table — does NOT touch
your LinkedIn at all. We surface the PERSON + their profile URL + WHY
they're worth engaging with today. you opens LinkedIn himself in his
real browser, browses their feed, and comments naturally.

Selection logic:
  1. Newest discoveries first (created in last 24h) — keeps the rotation fresh
  2. Then highest relevance_score that hasn't been engaged with in 14+ days
  3. Cap at 5

No post-tracking. No Unipile calls. No BU scrapes. Zero automation footprint
on your LinkedIn account.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

from shared.db import db
from shared.logging.logger import AgentLogger
from shared.notifications.slack import SlackNotifier

_log = AgentLogger("influencer-daily-brief")

DASHBOARD_URL = os.getenv(
    "DASHBOARD_URL", "https://your-dashboard.up.railway.app"
)


def _pick_todays_five() -> list[dict]:
    """Return 5 LinkedIn influencers you should engage with today.

    Prioritizes: newly-discovered (last 24h) → stale-engagement (>=14d ago) →
    highest relevance score among never-engaged.
    """
    now = datetime.now(timezone.utc)
    fresh_cutoff = (now - timedelta(days=1)).isoformat()
    stale_cutoff = (now - timedelta(days=14)).isoformat()

    # 1. New this week
    fresh = (
        db().table("influencers").select("*")
        .eq("platform", "linkedin").eq("status", "tracked")
        .gte("created_at", fresh_cutoff)
        .order("relevance_score", desc=True).limit(5).execute().data or []
    )
    picks: list[dict] = list(fresh)

    if len(picks) < 5:
        # 2. Top-scored never engaged
        never = (
            db().table("influencers").select("*")
            .eq("platform", "linkedin").eq("status", "tracked")
            .is_("last_engaged_at", "null")
            .order("relevance_score", desc=True)
            .limit(5 - len(picks)).execute().data or []
        )
        already = {p["id"] for p in picks}
        picks.extend(p for p in never if p["id"] not in already)

    if len(picks) < 5:
        # 3. Stale (last engaged >= 14d ago), highest score first
        stale = (
            db().table("influencers").select("*")
            .eq("platform", "linkedin").eq("status", "tracked")
            .lte("last_engaged_at", stale_cutoff)
            .order("relevance_score", desc=True)
            .limit(5 - len(picks)).execute().data or []
        )
        already = {p["id"] for p in picks}
        picks.extend(p for p in stale if p["id"] not in already)

    return picks[:5]


def _format(inf: dict) -> str:
    name = inf.get("full_name") or inf.get("handle") or "?"
    headline = (inf.get("headline") or "").strip()
    url = inf.get("profile_url") or "#"
    score = inf.get("relevance_score") or 0
    why = ((inf.get("metadata") or {}).get("why") or "").strip()
    line = f"  • <{url}|*{name}*> · score {score}"
    if headline:
        line += f"\n      _{headline[:120]}_"
    if why:
        line += f"\n      → {why[:160]}"
    return line


async def send() -> None:
    """Cron entrypoint — runs daily 6am UTC."""
    picks = _pick_todays_five()
    if not picks:
        _log.log("nothing_to_brief")
        try:
            await SlackNotifier().send(
                "dm",
                ":eyes: *Today's 5 LinkedIn people to engage with*\n\n"
                "_(no tracked influencers yet — discovery hasn't seeded any.)_",
                "influencer-daily-brief", priority="normal",
            )
        except Exception:
            pass
        return

    lines = [
        ":eyes: *Today's 5 LinkedIn people to engage with*",
        "_Open each profile, browse their recent posts, drop a substantive "
        "comment on one or two. You're commenting from your own browser — "
        "the system never touches your LinkedIn._",
        "",
    ]
    lines.extend(_format(inf) for inf in picks)
    lines.append("")
    lines.append(f":speech_balloon: Posts to comment on: {DASHBOARD_URL}/comments")

    try:
        await SlackNotifier().send(
            "dm", "\n".join(lines), "influencer-daily-brief", priority="normal"
        )
    except Exception as e:
        _log.error("slack_send_failed", str(e))

    _log.log("brief_sent", metadata={"linkedin": len(picks)})


if __name__ == "__main__":
    asyncio.run(send())
