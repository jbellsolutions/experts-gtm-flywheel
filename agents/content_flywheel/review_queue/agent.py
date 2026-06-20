"""Review queue — assembles batches for your morning Slack ping + weekly digest."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx

from shared.auth.vault import get_secret
from shared.db import db
from shared.logging.logger import AgentLogger

_log = AgentLogger("review-queue")

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://your-dashboard.up.railway.app")


async def _slack_dm(text: str) -> None:
    user_id = os.getenv("SLACK_OPERATOR_USER_ID")
    if not user_id:
        _log.log("slack_skipped_no_user_id", metadata={"text_preview": text[:80]})
        return
    token = get_secret("SLACK_BOT_TOKEN")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": user_id, "text": text, "mrkdwn": True},
        )
        _log.log("slack_dm_sent",
                 metadata={"ok": r.json().get("ok"), "status": r.status_code})


async def assemble_morning_batch() -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()

    # Drafts due today
    drafts = db().table("drafts").select("platform").gte(
        "scheduled_for", today
    ).lt("scheduled_for", tomorrow).eq("status", "pending").execute().data or []
    by_platform: dict[str, int] = {}
    for d in drafts:
        by_platform[d["platform"]] = by_platform.get(d["platform"], 0) + 1

    parts = [f"*Morning, you.* Today's queue:"]
    if by_platform:
        for plat, n in sorted(by_platform.items()):
            parts.append(f"  • {plat}: {n} drafts to approve")
    else:
        parts.append("  • No drafts queued (last live not repurposed yet?)")
    parts.append(f"\n<{DASHBOARD_URL}/today|Open dashboard ›>")
    await _slack_dm("\n".join(parts))


async def weekly_digest() -> None:
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    published = db().table("drafts").select("platform").eq(
        "status", "published"
    ).gte("published_at", week_ago).execute().data or []
    by_platform: dict[str, int] = {}
    for d in published:
        by_platform[d["platform"]] = by_platform.get(d["platform"], 0) + 1

    # Engagement totals from latest snapshots for posts published this week
    pub_ids = [d.get("id") for d in (db().table("drafts").select("id, platform")
                                     .eq("status", "published")
                                     .gte("published_at", week_ago)
                                     .execute().data or [])]
    metrics_rows = []
    if pub_ids:
        metrics_rows = (db().table("post_metrics_latest")
                        .select("draft_id, platform, likes, comments, reposts, engagement, impressions")
                        .in_("draft_id", pub_ids).execute().data or [])
    eng_by_plat: dict[str, dict[str, int]] = {}
    for m in metrics_rows:
        plat = m["platform"]
        bucket = eng_by_plat.setdefault(plat, {"likes": 0, "comments": 0, "reposts": 0, "imp": 0})
        bucket["likes"] += m.get("likes") or 0
        bucket["comments"] += m.get("comments") or 0
        bucket["reposts"] += m.get("reposts") or 0
        bucket["imp"] += m.get("impressions") or 0

    # Top-3 by engagement
    top = sorted(metrics_rows, key=lambda r: r.get("engagement") or 0, reverse=True)[:3]

    lines = ["*Weekly digest — content flywheel*"]
    lines.append(f"\n*Published this week:* {sum(by_platform.values())} pieces")
    for plat, n in sorted(by_platform.items()):
        bucket = eng_by_plat.get(plat, {})
        eng = bucket.get("likes", 0) + bucket.get("comments", 0) + bucket.get("reposts", 0)
        if eng:
            lines.append(f"  • {plat}: {n} posts · {eng} engagements"
                         + (f" · {bucket['imp']} impressions" if bucket.get("imp") else ""))
        else:
            lines.append(f"  • {plat}: {n}")

    if top:
        lines.append("\n*Top 3 by engagement:*")
        for m in top:
            eng = m.get("engagement") or 0
            lines.append(f"  • {m['platform']} — {eng} engagements "
                         f"({m.get('likes') or 0}❤︎ / {m.get('comments') or 0}💬 / {m.get('reposts') or 0}↻)")

    lines.append(f"\n<{DASHBOARD_URL}/drafts?col=published|See full pipeline ›>")
    await _slack_dm("\n".join(lines))


async def run() -> None:
    return
