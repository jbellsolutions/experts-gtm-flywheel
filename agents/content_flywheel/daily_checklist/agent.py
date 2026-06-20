"""Daily checklist generator — runs at 5am ET (09:00 UTC) every day.

Generates a thorough, SOP-style checklist. Reads live state (drafts, inbox,
client follow-ups, weekly KPIs) and produces 15-22 items grouped by time block, plus
a KPI scoreboard. The dashboard's Today tab + the morning Slack DM both
read from the same row in `daily_checklists`.

Schema in the row:
{
  date,
  summary: short text shown at top,
  items: [{id, scope, label, description, target, completed, completed_at,
           system_field, system_value}],
  kpis: [{key, target, actual, label, pct}],
  context: {
    drafts_today: [{platform, format, pillar, body_preview}, ...],
    hot_leads: [{name, platform, score, problem_preview}, ...],
    followups: [{company, stage, next_action}, ...]
  }
}
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import httpx

from shared.auth.vault import get_secret
from shared.db import db
from shared.logging.logger import AgentLogger

from .kpis import WEEKLY_TARGETS, week_to_date

_log = AgentLogger("daily-checklist")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://your-dashboard.up.railway.app")
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _today_in_et() -> date:
    return (datetime.now(timezone.utc) - timedelta(hours=4)).date()


def _gather_context(today: date) -> dict:
    """Pull the specific drafts / hot leads / follow-ups to surface inline."""
    end = today + timedelta(days=1)

    # Drafts due today, ordered by scheduled time
    drafts = db().table("drafts").select(
        "id, platform, format, pillar, body, scheduled_for"
    ).eq("status", "pending").gte(
        "scheduled_for", today.isoformat()
    ).lt("scheduled_for", end.isoformat()).order("scheduled_for").execute().data or []

    drafts_today = [
        {
            "id": d["id"],
            "platform": d["platform"],
            "format": d["format"],
            "pillar": d["pillar"],
            "body_preview": (d.get("body") or "")[:120].strip(),
        }
        for d in drafts
    ]

    # Inbox + follow-ups retired — internal note
    hot_leads: list[dict] = []
    followups: list[dict] = []

    # Today's engage list — top influencer posts (LinkedIn) not yet engaged
    li_engage = (
        db().table("influencer_posts")
        .select("body, post_url, relevance_score, suggested_comment, "
                "influencers(handle, full_name, profile_url)")
        .eq("platform", "linkedin").eq("our_engagement_status", "none")
        .gte("relevance_score", 60)
        .order("relevance_score", desc=True).limit(5).execute().data or []
    )
    # System health — publishing pipeline state
    drafts_all = db().table("drafts").select("status").execute().data or []
    from collections import Counter
    status_counts = dict(Counter(d["status"] for d in drafts_all))

    # Last poll info
    kv = db().table("kv_state").select("key, value").in_(
        "key", ["inbound_last_poll"]
    ).execute().data or []
    last_polls = {r["key"]: r["value"] for r in kv}

    return {
        "drafts_today": drafts_today,
        "hot_leads": hot_leads,
        "followups": followups,
        "li_engage": li_engage,
        "status_counts": status_counts,
        "last_polls": last_polls,
    }


def _draft_breakdown(drafts: list[dict]) -> str:
    """Return a short string like '3 LI · 1 Substack'."""
    counts: dict[str, int] = {}
    plat_label = {
        "linkedin": "LI", "substack": "Substack",
        "medium": "Medium", "newsletter": "Newsletter",
    }
    for d in drafts:
        label = plat_label.get(d["platform"], d["platform"])
        counts[label] = counts.get(label, 0) + 1
    if not counts:
        return "0"
    return " · ".join(f"{n} {k}" for k, n in counts.items())


def _build_items(today: date, context: dict) -> tuple[list[dict], str]:
    """Build the checklist. Each item: id, scope, label, description, target."""
    weekday = today.weekday()
    weekday_name = WEEKDAY_NAMES[weekday]

    drafts_today = context["drafts_today"]
    hot_leads = context["hot_leads"]
    followups = context["followups"]
    n_drafts = len(drafts_today)
    n_hot = len(hot_leads)
    n_followups = len(followups)

    items: list[dict] = []

    # ── Morning (5:30-7am) — Triage & Approve ─────────────────────────────
    items.append({
        "id": "morning-scan",
        "scope": "morning",
        "label": "Open dashboard, scan today's posture",
        "description": "Glance at draft count, inbox count, follow-up count, and the KPI scoreboard. 60 seconds.",
        "target": "60 sec",
    })

    items.append({
        "id": "morning-approve-drafts",
        "scope": "morning",
        "label": (
            f"Approve {n_drafts} draft{'s' if n_drafts != 1 else ''} due today"
            + (f" ({_draft_breakdown(drafts_today)})" if n_drafts else "")
        ),
        "description": (
            "Open the Drafts tab. Read each draft, edit one sentence to make it "
            "more 'you', approve. Bulk-approve if rushed. LinkedIn and Newsletter "
            "publish themselves at scheduled slots; Substack and Medium publish "
            "via Browser Use Cloud under their captured profiles."
        ),
        "target": "All due today approved before 7am",
        "system_field": "drafts_today",
        "system_value": n_drafts,
    })

    # ── Engage Out (10-11am) — Go to where conversations are ──────────────
    items.append({
        "id": "engage-linkedin-comments",
        "scope": "engage",
        "label": "Drop 5 substantive comments on others' LinkedIn posts",
        "description": (
            "Find 5 posts in your feed where you can add real value — not 'great post!'. "
            "2-3 sentences that ANSWER something or share specific experience from a "
            "real client engagement. This is how you earn impressions in the algorithm."
        ),
        "target": "5/day = 25/wk",
    })

    # ── Midday (12-12:30pm) — Sweep ───────────────────────────────────────
    items.append({
        "id": "midday-dms",
        "scope": "midday",
        "label": "New DMs since morning + YouTube comment replies",
        "description": (
            "Refresh the Inbox tab. Reply to anything new, mark hot leads, snooze cold ones. "
            "Then hop on YouTube channel page and reply to top comments on the last 2 videos. "
            "Heart all good comments, pin the best one per video."
        ),
        "target": "0 unread at end of midday",
    })

    items.append({
        "id": "midday-capture-stories",
        "scope": "midday",
        "label": "Capture story ideas from morning conversations",
        "description": (
            "Anything from this morning's DMs/comments worth turning into content? "
            "A specific problem someone shared, a client win, a quote from a customer. "
            "Drop it in your notes app under 'Live Material'. Future-you will thank you."
        ),
        "target": "1-3 story seeds/day",
    })

    # ── Recording days ────────────────────────────────────────────────────
    if weekday == 1:  # Tuesday — Pillar 1
        items.extend([
            {
                "id": "record-prep-pillar1",
                "scope": "afternoon",
                "label": "🎥 Pre-record prep — pick the live's problem",
                "description": (
                    "15 min before going live: review your 'Live Material' notes from "
                    "the week. Pick the single most relatable business problem someone "
                    "shared in DMs/comments. This is what you'll solve live. Don't pick "
                    "the most technical — pick the one that 80% of viewers will recognize."
                ),
                "target": "1 specific problem chosen + screen-share setup tested",
            },
            {
                "id": "record-live-pillar1",
                "scope": "afternoon",
                "label": "🎥 Record Pillar 1 live (45-60 min)",
                "description": (
                    "Pillar 1 — 'Ask me anything, I'll just tell you.' Open with the "
                    "problem you picked. Solve it on screen. Read comments live, take "
                    "additional problems if time. Don't script. Real, conversational, "
                    "generous. End with: 'Drop your problem in the comments, I'll "
                    "answer them all this week.'"
                ),
                "target": "45-60 min recorded, multi-platform live (StreamYard/Restream)",
            },
            {
                "id": "record-post-pillar1",
                "scope": "afternoon",
                "label": "🎥 Post-record (10 min)",
                "description": (
                    "Drop a "
                    "'thanks for joining' message in your community. Don't worry "
                    "about repurposing — the 10pm cron pulls the transcript and "
                    "generates 22 drafts overnight."
                ),
                "target": "thank-you note posted to your community",
            },
        ])
    elif weekday == 3:  # Thursday — Pillar 2
        items.extend([
            {
                "id": "record-prep-pillar2",
                "scope": "afternoon",
                "label": "🎥 Pre-record prep — pick the journey angle",
                "description": (
                    "Pick ONE of: a client win this week, a customer story, "
                    "a behind-the-scenes from training, or a philosophy point about "
                    "the certification. Don't try to cover all of it — go deep on one."
                ),
                "target": "1 angle chosen + supporting evidence ready",
            },
            {
                "id": "record-live-pillar2",
                "scope": "afternoon",
                "label": "🎥 Record Pillar 2 live (45-60 min)",
                "description": (
                    "Pillar 2 — The Journey. Tell the story. Show the work. Talk about "
                    "what's hard and what's working. End with the implicit 'we have a "
                    "team that can solve your problem' — never explicit. Authority "
                    "comes from the realness, not the pitch."
                ),
                "target": "45-60 min recorded, simulcast LIVE",
            },
            {
                "id": "record-post-pillar2",
                "scope": "afternoon",
                "label": "🎥 Post-record (10 min)",
                "description": (
                    "Update your community with the client win or "
                    "graduate story you just shared. Tag the graduate if you mentioned "
                    "them by name."
                ),
                "target": "Done before EOD",
            },
        ])

    # ── Evening (5:30-6pm) ────────────────────────────────────────────────
    items.append({
        "id": "evening-tomorrow-prep",
        "scope": "evening",
        "label": "Set tomorrow's intentions",
        "description": (
            "Anything that needs prep? Sales call to prepare for? Recording day "
            "tomorrow (Tue/Thu)? Block 1 hour for tomorrow morning's flywheel work."
        ),
        "target": "Calendar blocked",
    })

    # ── Friday — Weekly review ────────────────────────────────────────────
    if weekday == 4:
        items.extend([
            {
                "id": "friday-read-digest",
                "scope": "friday",
                "label": "📊 Read the weekly Slack digest",
                "description": (
                    "Slack DM lands at 5pm with: pieces published this week by platform, "
                    "hot conversations started, new client follow-ups. Read it. Notice "
                    "what's outperforming."
                ),
                "target": "Read",
            },
            {
                "id": "friday-platform-metrics",
                "scope": "friday",
                "label": "📊 Check platform metrics vs targets",
                "description": (
                    "LinkedIn impressions (target 50K-150K/wk early, 150K+ steady-state). "
                    "Twitter impressions (target 50K+/wk). YouTube views (target 5K+/wk). "
                    "Substack subscribers (target +50/wk). Newsletter open rate (target 30%+). "
                    "Note any platform that's >2x ahead — double down there."
                ),
                "target": "All 5 platforms reviewed",
            },
            {
                "id": "friday-plan-lives",
                "scope": "friday",
                "label": "📊 Plan next week's 2 lives",
                "description": (
                    "Tue Pillar 1 topic — pick from this week's most-asked problems in DMs. "
                    "Thu Pillar 2 topic — pick from this week's biggest client win or customer "
                    "milestone. Add to your notes app under 'Next Week's Lives'."
                ),
                "target": "2 topics committed",
            },
            {
                "id": "friday-community-update",
                "scope": "friday",
                "label": "📊 Update your community with weekly recap",
                "description": (
                    "Post a short weekly recap: top 3 wins, top 3 content pieces, "
                    "anything important happening next week. This is what makes the "
                    "community feel alive."
                ),
                "target": "Posted",
            },
        ])

    # ── Summary line ──────────────────────────────────────────────────────
    parts = [f"*{weekday_name}* — {n_drafts} draft(s) due"]
    if weekday == 1:
        parts.append("📹 RECORDING DAY (Pillar 1 — problem-solving)")
    elif weekday == 3:
        parts.append("📹 RECORDING DAY (Pillar 2 — journey)")
    if weekday == 4:
        parts.append("📊 weekly review tonight")
    summary = " · ".join(parts)

    return items, summary


# ── Slack DM formatting ──────────────────────────────────────────────────────

SCOPE_HEADERS = [
    ("morning",   "🌅 *MORNING (15-20 min — triage & approve)*"),
    ("engage",    "🤝 *ENGAGE OUT (30-45 min — grow the audience)*"),
    ("midday",    "🍽️ *MIDDAY (10 min — sweep)*"),
    ("afternoon", "🕒 *AFTERNOON*"),
    ("evening",   "🌙 *EVENING (10 min — wrap)*"),
    ("friday",    "📊 *FRIDAY WEEKLY REVIEW (30 min)*"),
]


def _format_slack_message(items: list[dict], summary: str, kpis: dict, context: dict) -> str:
    lines = ["*Good morning. Today's plan:*", f"_{summary}_", ""]

    # KPI scoreboard (top 5 most-relevant)
    lines.append("*Week so far:*")
    keys = ["conversations_started", "linkedin_posts_published",
            "substack_posts_published", "medium_articles_published",
            "newsletter_sent", "leads_new", "lives_recorded"]
    for key in keys:
        k = kpis.get(key)
        if not k:
            continue
        bar = "▓" * (k["pct"] // 10) + "░" * (10 - k["pct"] // 10)
        lines.append(f"  `{bar}` {k['actual']}/{k['target']} {k['label']}")
    lines.append("")

    # Group items by scope
    by_scope: dict[str, list[dict]] = {}
    for item in items:
        by_scope.setdefault(item.get("scope", "other"), []).append(item)

    for scope, header in SCOPE_HEADERS:
        scope_items = by_scope.get(scope, [])
        if not scope_items:
            continue
        lines.append(header)
        for item in scope_items:
            target = f"  _→ {item['target']}_" if item.get("target") else ""
            lines.append(f"  ☐ {item['label']}")
            if target:
                lines.append(target)
        lines.append("")

    # Influencer engage list (LinkedIn only)
    li_engage = context.get("li_engage") or []
    if li_engage:
        lines.append("*Today's engage list:*")
        lines.append(f"  💬 LinkedIn ({len(li_engage)}):")
        for p in li_engage[:5]:
            inf = p.get("influencers") or {}
            name = inf.get("full_name") or inf.get("handle") or "?"
            url = p.get("post_url") or inf.get("profile_url") or "#"
            snippet = (p.get("body") or "").replace("\n", " ")[:90]
            lines.append(f"    • <{url}|{name}>: {snippet}…")
        lines.append(f"  <{DASHBOARD_URL}/comments|All →>")
        lines.append("")

    # System health — only show if anything's notable
    sc = context.get("status_counts") or {}
    failed_n = sc.get("failed", 0)
    pending_n = sc.get("pending", 0)
    approved_n = sc.get("approved", 0)
    health_bits = []
    if failed_n:
        health_bits.append(f":warning: {failed_n} failed (<{DASHBOARD_URL}/drafts?col=failed|review →>)")
    if pending_n:
        health_bits.append(f"📝 {pending_n} pending approval")
    if approved_n:
        health_bits.append(f"✅ {approved_n} approved & queued")
    if health_bits:
        lines.append("*Pipeline:* " + " · ".join(health_bits))
        lines.append("")

    lines.append(f"<{DASHBOARD_URL}/today|Open dashboard ›>")
    return "\n".join(lines)


async def _slack_dm(text: str) -> None:
    """Send the morning brief to one or more recipients.

    Target resolution:
      - Primary: SLACK_CHANNEL_OVERRIDE (a channel id) takes precedence — used
        by client deployments like Tony's, where the brief goes to a shared
        channel. Otherwise SLACK_OPERATOR_USER_ID / OPERATOR_SLACK_USER_ID (a DM).
      - Extra: SLACK_EXTRA_RECIPIENTS — a comma-separated list of additional
        user or channel ids that also receive the brief. Set per-deploy, so e.g.
        your organic flywheel can CC a partner (a teammate) on every brief while
        Tony's deployment leaves it unset.

    For private channels the bot hasn't been added to, Slack returns
    channel_not_found; we then fall back to SLACK_USER_TOKEN, which can post
    to any channel the authed user is in. Removes the manual /invite step.
    """
    primary = (
        os.getenv("SLACK_CHANNEL_OVERRIDE")
        or os.getenv("SLACK_OPERATOR_USER_ID")
        or os.getenv("OPERATOR_SLACK_USER_ID")
    )
    extra = [t.strip() for t in os.getenv("SLACK_EXTRA_RECIPIENTS", "").split(",") if t.strip()]
    # primary first, then extras, de-duped preserving order
    seen: set = set()
    targets = [t for t in [primary, *extra] if t and not (t in seen or seen.add(t))]
    if not targets:
        _log.log("slack_skipped_no_target")
        return

    bot_token = get_secret("SLACK_BOT_TOKEN")
    user_token = os.getenv("SLACK_USER_TOKEN", "")
    membership_errors = {"channel_not_found", "not_in_channel"}

    async with httpx.AsyncClient(timeout=15) as client:
        for target in targets:
            payload = {"channel": target, "text": text, "mrkdwn": True}
            r = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {bot_token}"},
                json=payload,
            )
            data = r.json()
            if (not data.get("ok") and data.get("error") in membership_errors
                    and user_token):
                r2 = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {user_token}"},
                    json=payload,
                )
                data = r2.json()
            if not data.get("ok"):
                _log.error("slack_dm_failed", data.get("error", "unknown"),
                           metadata={"target": target})
            else:
                _log.log("slack_dm_sent", metadata={"target": target})


async def generate_today() -> None:
    today = _today_in_et()
    _log.log("generate_start", metadata={"date": today.isoformat()})

    context = _gather_context(today)
    items, summary = _build_items(today, context)
    kpis = week_to_date(today)

    # Initialize each item with completion fields
    for item in items:
        item.setdefault("completed", False)
        item.setdefault("completed_at", None)

    db().table("daily_checklists").upsert({
        "date": today.isoformat(),
        "items": items,
        "summary": summary,
        "kpis": kpis,
        "context": context,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="date").execute()

    await _slack_dm(_format_slack_message(items, summary, kpis, context))
    _log.log("generate_done",
             metadata={"date": today.isoformat(), "items": len(items)})


async def run() -> None:
    return
