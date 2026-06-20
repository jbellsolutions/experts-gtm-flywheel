"""Assign drafts to weekday × time-of-day slots.

Mirrors the calendar in the strategy doc:
  LinkedIn: 3 posts/day — morning / midday / mid-afternoon ET
  Substack: weekly Mon 12:00
  Medium:   Wed 09:00 (Pillar 1 article) + Fri 09:00 (Pillar 2 article)
  Newsletter: daily 8am ET, one per day
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

# 3 LinkedIn posts/day, stored in UTC. Each time is chosen to land in a
# different publisher cron window (crons fire 11/16/19/21 UTC = 7am/12pm/3pm/5pm
# ET), so the three posts publish spread across the day:
#   10:30 UTC -> 7am ET  (morning)
#   15:30 UTC -> 12pm ET (midday / early afternoon)
#   18:30 UTC -> 3pm ET  (mid-afternoon)
LI_SLOTS = (time(10, 30), time(15, 30), time(18, 30))
SUBSTACK_SLOT = (0, time(12, 0))   # weekday=Monday
MEDIUM_P1_SLOT = (2, time(9, 0))   # Wednesday
MEDIUM_P2_SLOT = (4, time(9, 0))   # Friday
# 8am ET = 12:00 UTC (EDT, UTC-4). Slots store UTC; earlier code set hour=8 on a
# UTC datetime, which rendered as 4am ET — the bug you saw.
NEWSLETTER_SLOT_UTC = time(12, 0)


def _next_free_newsletter_day(base: datetime) -> datetime:
    """Spread newsletters one-per-day. Schedule the new one for the day after
    the latest already-scheduled newsletter (pending/approved), or tomorrow if
    none. Prevents the 'five newsletters all on Friday' bunching when many
    ideas drain in one batch."""
    earliest = (base + timedelta(days=1)).replace(
        hour=NEWSLETTER_SLOT_UTC.hour, minute=0, second=0, microsecond=0)
    try:
        from shared.db import db
        rows = (db().table("drafts").select("scheduled_for")
                .eq("platform", "newsletter")
                .in_("status", ["pending", "approved", "edited"])
                .order("scheduled_for", desc=True).limit(1).execute().data or [])
        if rows and rows[0].get("scheduled_for"):
            last = datetime.fromisoformat(rows[0]["scheduled_for"].replace("Z", "+00:00"))
            nxt = (last + timedelta(days=1)).replace(
                hour=NEWSLETTER_SLOT_UTC.hour, minute=0, second=0, microsecond=0)
            return max(earliest, nxt)
    except Exception:
        pass
    return earliest


def next_weekday(after: datetime, target_weekday: int) -> datetime:
    days = (target_weekday - after.weekday()) % 7
    return after + timedelta(days=days or 7)


def assign(platform: str, format_: str, pillar: str, idx: int, base: datetime) -> datetime:
    """Return scheduled_for for the (platform, format, pillar, idx) draft.

    `idx` is the position within that platform's batch (0-based).
    `base` is the moment the repurposer ran (Tue/Thu 22:30).
    """
    if platform == "linkedin" and format_ == "post":
        # 3 posts/day, spread morning / midday / mid-afternoon (LI_SLOTS).
        n = len(LI_SLOTS)
        day = base + timedelta(days=1 + idx // n)
        slot = LI_SLOTS[idx % n]
        return day.replace(hour=slot.hour, minute=slot.minute, second=0, microsecond=0)
    if platform == "substack":
        wd, slot = SUBSTACK_SLOT
        d = next_weekday(base, wd)
        return d.replace(hour=slot.hour, minute=slot.minute, second=0, microsecond=0)
    if platform == "medium":
        wd, slot = MEDIUM_P2_SLOT if pillar == "2" else MEDIUM_P1_SLOT
        d = next_weekday(base, wd)
        return d.replace(hour=slot.hour, minute=slot.minute, second=0, microsecond=0)
    if platform == "newsletter":
        # One per day at 8am ET, spread (day after the latest scheduled one).
        return _next_free_newsletter_day(base)
    # default: tomorrow morning
    return (base + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
