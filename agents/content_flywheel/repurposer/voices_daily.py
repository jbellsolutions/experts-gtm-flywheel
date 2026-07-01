"""Daily three-voice LinkedIn engine.

Once a day (evening-prior) this builds exactly THREE LinkedIn posts for the next
day — one per voice — each a concatenation of:

    brand voice  ×  current trend / recent event  ×  industry-specific use case

That combination is what wins (your best post = a recent legal event × the
AI-in-legal trend × his voice). The trend comes from the existing trends scraper
(`content_ideas`, source='auto_trend'); the industry is rotated so the day's
three posts and successive days cover different business categories; the model
derives the concrete industry use case from the trend.

Same quality engine as everywhere else: `brand_voice.system_prompt(...)` on the
`linkedin_post` Sonnet tier + `passes_qa`. your brand posts first (morning). Visuals,
approval, and publishing are unchanged downstream.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from shared.db import db
from shared.logging.logger import AgentLogger

from . import brand_voice, editorial, voices
from .llm import complete
from .pillar_classifier import classify
from ..idea_queue import store as idea_store

_log = AgentLogger("voices_daily")

# your brand leads in the morning; POV voices follow midday / mid-afternoon (UTC).
# Two posts/day: your brand flagship at 8am ET, ONE alternating POV voice at 2pm ET.
# Slots store UTC (scheduled_for is UTC); ET = UTC-4 (EDT). Setting hour=8 literally
# would render as 4am ET — the bug we already hit on Speaker Agent. So:
#   8am ET -> 12:00 UTC ; 2pm ET -> 18:00 UTC.
# Both POV voices share the 2pm slot because only one of them runs on a given day.
VOICE_SLOT: dict[str, time] = {
    "ai_guy": time(12, 0),
    "human_loop": time(18, 0),
    "ai_reality": time(18, 0),
}

_TREND_FETCH = 20          # how many recent trend items to consider
_USED_TREND_CAP = 200      # per-voice memory of consumed trends


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── rotation state (kv_state) ────────────────────────────────────────────────

def _next_industry() -> str:
    """Round-robin the global industry index; each call advances by one so the
    day's three posts land on three different categories and days vary."""
    i = int(idea_store.kv_get("voices_industry_idx", 0) or 0)
    industry = voices.INDUSTRIES[i % len(voices.INDUSTRIES)]
    idea_store.kv_set("voices_industry_idx", i + 1)
    return industry


def _next_cta(voice: str) -> str:
    bank = voices.get(voice).cta_bank or voices.DEFAULT_CTAS
    key = f"voices_cta_idx:{voice}"
    i = int(idea_store.kv_get(key, 0) or 0)
    idea_store.kv_set(key, i + 1)
    return bank[i % len(bank)]


def _used_trends(voice: str) -> list[str]:
    return list(idea_store.kv_get(f"voices_used_trend:{voice}", []) or [])


def _remember_trend(voice: str, tid: str) -> None:
    used = (_used_trends(voice) + [tid])[-_USED_TREND_CAP:]
    idea_store.kv_set(f"voices_used_trend:{voice}", used)


# ── source material ──────────────────────────────────────────────────────────

def _recent_trends() -> list[dict]:
    """Freshest AI-news items the trends scraper deposited (newest first)."""
    rows = (db().table("content_ideas").select("id,content,metadata")
            .eq("source", "auto_trend").eq("status", "pending")
            .order("created_at", desc=True).limit(_TREND_FETCH).execute().data or [])
    return rows


def _trend_id(t: dict) -> str:
    return ((t.get("metadata") or {}).get("source_id")) or t.get("id") or t.get("content", "")[:60]


def _pick_trend(voice: str, trends: list[dict], taken: set[str]) -> dict | None:
    used = set(_used_trends(voice)) | taken
    for t in trends:
        if _trend_id(t) not in used:
            return t
    return None


def _ai_guy_idea() -> dict | None:
    """ai_guy may lead with a queued you idea (Slack/transcript) over a trend."""
    for idea in idea_store.pending_ideas(limit=5):
        if idea.get("source") in ("slack", "transcript"):
            return idea
    return None


# ── scheduling ───────────────────────────────────────────────────────────────

def _slot_for(voice: str, base: datetime) -> str:
    """Next-day fixed slot for this voice; if taken, roll to the next free day."""
    slot = VOICE_SLOT[voice]
    day = (base + timedelta(days=1)).replace(
        hour=slot.hour, minute=slot.minute, second=0, microsecond=0)
    for _ in range(14):
        exists = (db().table("drafts").select("id")
                  .eq("platform", "linkedin").eq("format", "post")
                  .eq("scheduled_for", day.isoformat())
                  .in_("status", ["pending", "approved", "edited"])
                  .limit(1).execute().data or [])
        if not exists:
            return day.isoformat()
        day = day + timedelta(days=1)
    return day.isoformat()


# ── generation ───────────────────────────────────────────────────────────────

def _build_user_prompt(voice: str, trend_text: str, industry: str,
                       idea_seed: str | None) -> str:
    src = idea_seed or trend_text
    return (
        "Write today's LinkedIn post.\n\n"
        f"CURRENT TREND / RECENT EVENT to anchor it to:\n{src}\n\n"
        f"INDUSTRY LENS: {industry}\n\n"
        "Tie this current development to a concrete, real-world use case in that "
        "industry — something a person working there would immediately recognize "
        "and relate to. Be specific and recent. Stay fully in your voice. Do not "
        "say the words 'trend' or 'industry lens' or mention that you were given a "
        "prompt — just write the post as if it's your own timely take."
    )


def _make_post(voice: str, trends: list[dict], taken: set[str]) -> dict | None:
    industry = _next_industry()
    cta = _next_cta(voice)

    idea_seed = None
    trend = _pick_trend(voice, trends, taken)
    if voice == "ai_guy" and not trend:
        idea = _ai_guy_idea()
        idea_seed = idea["content"] if idea else None
    if not trend and not idea_seed:
        # fall back to one of the voice's own bank directions as the hook
        vp = voices.get(voice)
        if vp.few_shots:
            idx = int(idea_store.kv_get(f"voices_dir_idx:{voice}", 0) or 0)
            idea_seed = vp.few_shots[idx % len(vp.few_shots)]
            idea_store.kv_set(f"voices_dir_idx:{voice}", idx + 1)

    trend_text = (trend or {}).get("content", "") if trend else (idea_seed or "")
    if not trend_text:
        _log.log("no_source", metadata={"voice": voice})
        return None

    system = brand_voice.system_prompt("linkedin", voice=voice, cta=cta)
    user = _build_user_prompt(voice, trend_text, industry, idea_seed)
    try:
        body = complete("linkedin_post", system, user)
    except Exception as e:  # noqa: BLE001
        _log.error("voice_generate_failed", str(e), metadata={"voice": voice})
        return None
    if not body:
        return None

    ok, issues = brand_voice.passes_qa(body)
    pillar = classify(body) if voice == "ai_guy" else "both"
    tid = _trend_id(trend) if trend else f"seed:{voice}"
    taken.add(tid)
    if trend:
        _remember_trend(voice, tid)

    return {
        "platform": "linkedin", "format": "post", "pillar": pillar, "body": body,
        "metadata": {
            "voice": voice,
            "trend": trend_text[:300],
            "trend_url": ((trend or {}).get("metadata") or {}).get("url"),
            "industry": industry,
            "cta": cta,
            "decided_by": "voices_daily",
            **({"qa_issues": issues} if not ok else {}),
        },
        "scheduled_for": _slot_for(voice, _now()),
        "status": "pending",
    }


def rerun_one(draft: dict) -> dict | None:
    """Regenerate an existing voice draft in place (fresh trend/industry/CTA).

    Keeps the draft's id, slot, and status; returns the columns to update (new
    body + metadata, visual cleared so the visuals cron re-renders). The dashboard
    "Rerun" button flags `metadata.rerun_requested_at`; `rerun_drain` calls this.
    """
    md = draft.get("metadata") or {}
    voice = md.get("voice") or "ai_guy"
    fresh = _make_post(voice, _recent_trends(), set())
    if not fresh:
        return None
    keep = {k: v for k, v in md.items()
            if k not in ("visual", "visual_error", "visual_error_at",
                         "rerun_requested_at", "qa_issues")}
    new_md = {**keep, **fresh["metadata"], "regenerated_at": _now().isoformat()}
    return {"body": fresh["body"], "pillar": fresh["pillar"],
            "metadata": new_md, "status": "pending"}


async def rerun_drain() -> None:
    """Cron — regenerate any draft the dashboard flagged for rerun."""
    rows = (db().table("drafts").select("id,metadata,platform,format")
            .not_.is_("metadata->>rerun_requested_at", "null")
            .limit(5).execute().data or [])
    if not rows:
        return
    _log.log("rerun_start", metadata={"count": len(rows)})
    for r in rows:
        try:
            upd = rerun_one(r)
            if upd:
                db().table("drafts").update(upd).eq("id", r["id"]).execute()
                _log.log("rerun_done", metadata={"draft_id": r["id"],
                         "voice": upd["metadata"].get("voice")})
            else:
                # couldn't regenerate → just clear the flag so we don't loop
                md = {k: v for k, v in (r.get("metadata") or {}).items()
                      if k != "rerun_requested_at"}
                db().table("drafts").update({"metadata": md}).eq("id", r["id"]).execute()
        except Exception as e:  # noqa: BLE001
            _log.error("rerun_failed", str(e), metadata={"draft_id": r["id"]})


def _at(hour: int, minute: int) -> str:
    """Next-day timestamp at a fixed UTC time."""
    d = (_now() + timedelta(days=1)).replace(hour=hour, minute=minute,
                                             second=0, microsecond=0)
    return d.isoformat()


def _make_longform(kind: str, voice: str, platform: str, format_: str,
                   slot: str, trends: list[dict], taken: set[str]) -> dict | None:
    """Build one long-form piece (newsletter or article) via the editorial
    pipeline, anchored to a current trend × industry, in the given voice."""
    industry = _next_industry()
    cta = _next_cta(voice)
    trend = _pick_trend(voice, trends, taken)
    trend_text = (trend or {}).get("content", "") if trend else ""
    if not trend_text:  # fall back to a bank direction as the seed
        vp = voices.get(voice)
        trend_text = vp.few_shots[0] if vp.few_shots else f"AI in {industry}"
    seed = (
        f"{trend_text}\n\n"
        f"INDUSTRY FOCUS: {industry}\n\n"
        f"Anchor this piece to the current development above and make it a "
        f"concrete, relatable {industry} use case. Stay fully in voice. "
        f"End with this call to action, in your own words: {cta}"
    )
    body, extra = editorial.write_long_form(seed, platform, format_, "both", 0, voice=voice)
    if not body:
        _log.log("longform_failed", metadata={"kind": kind, "voice": voice})
        return None
    tid = _trend_id(trend) if trend else f"seed:{kind}"
    taken.add(tid)
    if trend:
        _remember_trend(voice, tid)
    return {
        "platform": platform, "format": format_, "pillar": "both", "body": body,
        "metadata": {
            "voice": voice, "kind": kind,
            "trend": trend_text[:300],
            "trend_url": ((trend or {}).get("metadata") or {}).get("url"),
            "industry": industry, "cta": cta,
            "decided_by": "voices_daily", **extra,
        },
        "scheduled_for": slot, "status": "pending",
    }


async def generate_daily_voices() -> None:
    """Cron entrypoint — produce tomorrow's content set:

    - 2 LinkedIn posts: your brand flagship (08:00) + ONE alternating POV voice
      (human_loop / ai_reality by day parity) at 14:00.
    - 1 newsletter in the ai_guy voice, alternating Kit <-> LinkedIn newsletter
    - 1 LinkedIn article, alternating human_loop <-> ai_reality
    All = voice x current trend x industry use case, through the same engine.
    """
    trends = _recent_trends()
    taken: set[str] = set()
    drafts: list[dict] = []

    # Day parity drives every daily alternation: the POV post voice, the article
    # voice, and the newsletter platform. The POV post and the article take the
    # TWO DIFFERENT secondary voices, so every day features all three voices
    # (your brand + Human-Loop + AI-Reality) instead of doubling one. The post voice
    # still alternates day to day.
    parity = (_now().date().toordinal()) % 2
    art_voice = "human_loop" if parity == 0 else "ai_reality"   # article (pre-existing alternation)
    pov_voice = "ai_reality" if parity == 0 else "human_loop"   # POV post = the other secondary voice

    # Two posts/day: your brand flagship (08:00) + one alternating POV voice (14:00).
    for voice in ("ai_guy", pov_voice):
        d = _make_post(voice, trends, taken)
        if d:
            drafts.append(d)

    # Daily newsletter — always your brand. Even day → Kit; odd day → LinkedIn newsletter.
    # 15:30 UTC lands in the 16:00 window (noon ET) — kept off the new 12:00/8am
    # window so the flagship post owns 8am and the newsletter stays at noon.
    if parity == 0:
        nl = _make_longform("newsletter", "ai_guy", "newsletter", "section",
                            _at(15, 30), trends, taken)
    else:
        nl = _make_longform("newsletter", "ai_guy", "linkedin", "newsletter",
                            _at(15, 30), trends, taken)
    if nl:
        # The Kit email newsletter flows hands-off: auto-approve it so the publisher
        # picks it up at its window (whether it SENDS vs. lands as a Kit draft is
        # governed by NEWSLETTER_AUTOSEND). The odd-day variant is a LinkedIn
        # newsletter (platform='linkedin') — leave it 'pending' so it respects the
        # LinkedIn auto-posting pause and the normal review gate.
        if nl.get("platform") == "newsletter":
            nl["status"] = "approved"
            nl["metadata"]["auto_approved"] = "voices_daily:newsletter"
        drafts.append(nl)

    # Daily LinkedIn article — art_voice (set above) is the opposite secondary
    # voice from today's POV post. 18:30 UTC lands in the 19:00 window (3pm ET) —
    # kept past the new 18:00/2pm window so the POV post owns 2pm, article stays 3pm.
    art = _make_longform("article", art_voice, "linkedin", "article",
                        _at(18, 30), trends, taken)
    if art:
        drafts.append(art)

    if drafts:
        db().table("drafts").insert(drafts).execute()
    _log.log("voices_daily_done", metadata={
        "drafts": len(drafts),
        "pieces": [f"{d['metadata'].get('voice')}/{d.get('format')}" for d in drafts],
        "industries": [d["metadata"].get("industry") for d in drafts],
        "trends_considered": len(trends),
    })


if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_daily_voices())
