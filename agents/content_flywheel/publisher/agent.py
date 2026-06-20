"""Publisher — pushes approved drafts to their target platforms."""
from __future__ import annotations

import importlib
import os
from datetime import datetime, timezone

from shared.db import db
from shared.logging.logger import AgentLogger
from shared.notifications.slack import SlackNotifier

_log = AgentLogger("publisher")

ADAPTERS: dict[str, str] = {
    "linkedin":   "agents.content_flywheel.publisher.linkedin",
    "substack":   "agents.content_flywheel.publisher.substack",
    "medium":     "agents.content_flywheel.publisher.medium",
    "newsletter": "agents.content_flywheel.publisher.newsletter",
}

# Long-form formats (one heavy piece per window, max) vs feed posts.
_LONGFORM = {"article", "newsletter", "section"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


def _mins_past_slot(draft: dict) -> float:
    s = draft.get("scheduled_for")
    if not s:
        return 1e9
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t).total_seconds() / 60.0
    except Exception:  # noqa: BLE001
        return 1e9


def _newsletter_sent_today() -> bool:
    """True if a Kit newsletter (platform='newsletter') has already been published
    today (UTC) — used to hard-cap newsletter sends at one per day."""
    start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
    try:
        rows = (db().table("drafts").select("id")
                .eq("platform", "newsletter").gte("published_at", start)
                .limit(1).execute().data or [])
        return len(rows) > 0
    except Exception:  # noqa: BLE001
        return False


def _window_selection(due: list[dict], posts_cap: int, longform_cap: int,
                      cover_deadline: int, newsletter_sent_today: bool = False) -> list[dict]:
    """Pick which due drafts publish THIS window so a bulk-approve backlog spreads
    across windows instead of dumping at once. `due` is scheduled_for-ASC, so the
    oldest pieces win the per-window slots; the rest are left untouched (still
    `approved`) and re-evaluated next window. Pure (no I/O) so it's unit-testable.

    - At most `posts_cap` feed posts + `longform_cap` long-form pieces per window.
    - The Kit newsletter (platform='newsletter') is hard-capped at ONE send per day
      (`newsletter_sent_today`, plus an in-run guard) — your rule for autosend.
    - A newsletter whose cover hasn't rendered is held until it does — bounded by
      `cover_deadline` minutes past its slot, after which it goes out cover-less
      rather than stranding the issue.
    """
    posts_done = longform_done = 0
    nl_done = newsletter_sent_today
    out: list[dict] = []
    for d in due:
        is_newsletter = d.get("platform") == "newsletter"
        is_longform = (d.get("format") or "post").lower() in _LONGFORM
        if is_newsletter:
            if nl_done:
                continue  # already sent today (or this run) — 1/day cap
            visual = (d.get("metadata") or {}).get("visual") or {}
            if visual.get("status") != "rendered" and _mins_past_slot(d) < cover_deadline:
                continue
        if is_longform:
            if longform_done >= longform_cap:
                continue
            longform_done += 1
        else:
            if posts_done >= posts_cap:
                continue
            posts_done += 1
        if is_newsletter:
            nl_done = True
        out.append(d)
    return out


async def publish_due() -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    # Accept both 'approved' (untouched) and 'edited' (you tweaked then approved).
    due = db().table("drafts").select("*").in_(
        "status", ["approved", "edited"]
    ).in_("platform", list(ADAPTERS.keys())).lte(
        "scheduled_for", now_iso
    ).is_("published_at", "null").order("scheduled_for").limit(50).execute().data or []

    posts_cap = _int_env("PUBLISH_POSTS_PER_WINDOW", 2)
    longform_cap = _int_env("PUBLISH_LONGFORM_PER_WINDOW", 1)
    cover_deadline = _int_env("NEWSLETTER_COVER_DEADLINE_MIN", 90)
    batch = _window_selection(due, posts_cap, longform_cap, cover_deadline,
                              newsletter_sent_today=_newsletter_sent_today())
    _log.log("publish_due_start", metadata={"due": len(due), "this_window": len(batch),
             "posts_cap": posts_cap, "longform_cap": longform_cap})
    notifier = SlackNotifier()

    for draft in batch:
        platform = draft["platform"]
        adapter_path = ADAPTERS.get(platform)
        if not adapter_path:
            _log.log("no_adapter", metadata={"platform": platform, "id": draft["id"]})
            continue
        try:
            adapter = importlib.import_module(adapter_path)
            result = await adapter.publish(draft)
            now = datetime.now(timezone.utc).isoformat()
            # Async adapters (substack, medium via browser_runner)
            # return {"queued": True}. They DON'T publish synchronously, so we
            # mustn't mark them published — browser_runner will when it's done.
            # We do mark a 'queued_at' so the dashboard can show "in flight".
            # Skip = adapter explicitly opted out (no path available, parked).
            # Don't churn the queue; mark as failed with skipped flag so
            # daily review can see it but cron doesn't keep retrying.
            if result.get("skip"):
                md = {**(draft.get("metadata") or {}),
                      "skipped": True,
                      "skip_reason": result.get("reason"),
                      "skip_hint": result.get("hint"),
                      "skipped_at": now}
                db().table("drafts").update({
                    "status": "failed",
                    "metadata": md,
                    "updated_at": now,
                }).eq("id", draft["id"]).execute()
                _log.log("skipped", metadata={
                    "platform": platform, "id": draft["id"],
                    "reason": result.get("reason")})
                continue
            if result.get("queued"):
                md = {**(draft.get("metadata") or {}), "queued_at": now}
                db().table("drafts").update({
                    "metadata": md,
                    "updated_at": now,
                }).eq("id", draft["id"]).execute()
                _log.log("queued_async", metadata={
                    "platform": platform, "id": draft["id"]})
                continue
            db().table("drafts").update({
                "status": "published",
                "published_at": now,
                "publish_url": result.get("url"),
                "updated_at": now,  # explicit; the table has no auto trigger
            }).eq("id", draft["id"]).execute()
            _log.log("published", metadata={"platform": platform, "id": draft["id"],
                                            "url": result.get("url")})
        except NotImplementedError as e:
            # Surface this so it shows up in Slack ops + the System Status widget.
            _log.log("adapter_not_ready",
                     metadata={"platform": platform, "id": draft["id"], "reason": str(e)})
            try:
                await notifier.send("ops",
                    f":construction: {platform} adapter not ready for draft "
                    f"{draft['id'][:8]}: {e}", "publisher", priority="low")
            except Exception:
                pass
        except Exception as e:
            now = datetime.now(timezone.utc).isoformat()
            db().table("drafts").update({
                "status": "failed",
                "metadata": {**(draft.get("metadata") or {}),
                             "error": str(e),
                             "failed_at": now},
                "updated_at": now,
            }).eq("id", draft["id"]).execute()
            _log.error("publish_failed", str(e),
                       metadata={"platform": platform, "id": draft["id"]})
            try:
                await notifier.send("ops",
                    f":warning: publish failed for {platform} draft {draft['id']}: {e}",
                    "publisher", priority="high")
            except Exception:
                pass


async def run() -> None:
    return
