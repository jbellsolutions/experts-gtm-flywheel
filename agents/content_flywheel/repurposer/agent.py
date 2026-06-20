"""Repurposer — transcript -> drafts for every platform.

Per transcript, generates:
  - 5 LinkedIn posts (Pillar 1 + Pillar 2 mix, slot-mapped across the week)
  - 1 LinkedIn article + 1 Medium mirror
  - 1 Substack narrative post
  - 1 newsletter section (Kit)

LinkedIn / Substack / Medium are the three publishing surfaces. Twitter,
Facebook, and Shorts were removed (see MIGRATION.md for date + reasons).

Models per task come from `model_config.MODELS` — swap there, not here.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from shared.db import db
from shared.logging.logger import AgentLogger

from . import brand_voice, editorial
from .llm import complete
from .pillar_classifier import classify
from .slot_mapper import assign, LI_SLOTS


def _reslot_linkedin(drafts: list[dict], base: datetime) -> None:
    """Spread this batch's LinkedIn *posts* across the 3-slots/day calendar,
    skipping (day, slot) pairs already taken by other scheduled LinkedIn posts.

    `slot_mapper.assign` only spreads within a single generation call and its
    per-target index resets, so multiple LinkedIn posts (across pillars, across
    ideas, or across overlapping runs) can collide on the same slot. This pass
    runs once after all drafts are built and reassigns every LinkedIn post to
    the next globally-free slot, keeping the real cadence at 3/day spread
    morning / midday / mid-afternoon.
    """
    li = [d for d in drafts if d.get("platform") == "linkedin" and d.get("format") == "post"]
    if not li:
        return
    start = (base + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    taken: set = set()
    try:
        rows = (db().table("drafts").select("scheduled_for")
                .eq("platform", "linkedin").eq("format", "post")
                .in_("status", ["pending", "approved", "edited"])
                .gte("scheduled_for", start.isoformat()).execute().data or [])
        for r in rows:
            sf = r.get("scheduled_for")
            if not sf:
                continue
            dt = datetime.fromisoformat(sf.replace("Z", "+00:00"))
            taken.add((dt.date(), (dt.hour, dt.minute)))
    except Exception:
        pass  # no DB / first run — just spread this batch from tomorrow

    day = start
    for d in li:
        placed = False
        while not placed:
            for s in LI_SLOTS:
                key = (day.date(), (s.hour, s.minute))
                if key not in taken:
                    taken.add(key)
                    d["scheduled_for"] = day.replace(
                        hour=s.hour, minute=s.minute, second=0, microsecond=0).isoformat()
                    placed = True
                    break
            if not placed:
                day = day + timedelta(days=1)

_log = AgentLogger("repurposer")

# (platform, format, pillar, count) — what we generate per transcript.
# NOTE: daily LinkedIn 'post' now comes from voices_daily.generate_daily_voices
# (one post per voice per day). Transcripts feed long-form only; the transcript
# itself still becomes ai_guy source material via the idea queue.
# Medium + Substack are SUNSET (extra platforms to watch, not auto-published).
# Daily LinkedIn posts, the LinkedIn article, and the newsletter (Kit + LinkedIn)
# are all owned by voices_daily.generate_daily_voices. So the transcript path
# generates nothing on its own now — the transcript still gets ingested and is
# available as ai_guy source material.
TARGETS: list[tuple[str, str, str, int]] = []

# (platform, format) -> task key in model_config.MODELS
TASK_FOR: dict[tuple[str, str], str] = {
    ("linkedin",  "post"):    "linkedin_post",
    ("linkedin",  "article"): "linkedin_article",
    ("substack",  "post"):    "substack_post",
    ("medium",    "article"): "medium_article",
    ("newsletter", "section"): "newsletter_section",
}

# (platform, format) -> brand_voice few-shot category
FEW_SHOT_FOR: dict[tuple[str, str], str] = {
    ("linkedin",  "post"):    "linkedin",
    ("linkedin",  "article"): "linkedin",
    ("substack",  "post"):    "substack_opener",
    ("medium",    "article"): "linkedin",
    ("newsletter", "section"): "linkedin",
}


# Long-form formats route through the 3-stage editorial pipeline (architect
# -> drafter -> editor). Everything else (LinkedIn posts) stays single-shot.
_LONG_FORM_FORMATS = {"article", "section"}


def _is_long_form(platform: str, format_: str) -> bool:
    if format_ in _LONG_FORM_FORMATS:
        return True
    if platform == "substack" and format_ == "post":
        return True
    return False


def _generate(transcript_text: str, platform: str, format_: str, pillar: str,
              idx: int, voice: str = "ai_guy") -> tuple[str | None, dict]:
    """Returns (body, extra_metadata). Extra metadata is stamped into the
    draft row's metadata field — primarily used to flag editorial_passes for
    long-form drafts so the dashboard can show which pieces went through the
    editorial team vs. single-shot."""
    pillar_for_prompt = (
        "1" if pillar in ("1", "both") and idx % 2 == 0
        else ("2" if pillar in ("2", "both") else pillar)
    )

    if _is_long_form(platform, format_):
        body, md = editorial.write_long_form(
            transcript_text, platform, format_, pillar_for_prompt, idx,
        )
        return body, md

    # Single-shot path (LinkedIn posts).
    fmt_key = FEW_SHOT_FOR.get((platform, format_), "linkedin")
    task = TASK_FOR.get((platform, format_), "linkedin_post")
    system = brand_voice.system_prompt(fmt_key, pillar_for_prompt, voice=voice)
    user = (
        f"Transcript excerpt from a YouTube live:\n\n"
        f"{transcript_text[:8000]}\n\n"
        f"Write one {format_} for {platform}, draft #{idx + 1}. "
        f"Pull a different idea from the transcript than the others would. "
        f"Output the post body only."
    )
    try:
        return complete(task, system, user), {}
    except Exception as e:
        _log.error("generate_failed", str(e),
                   metadata={"platform": platform, "format": format_, "idx": idx})
        return None, {}


async def repurpose_latest() -> None:
    _log.log("repurpose_start")

    # Newest transcript with no drafts yet
    transcripts = db().table("transcripts").select("*").order(
        "ingested_at", desc=True
    ).limit(5).execute().data or []
    target_t = None
    for t in transcripts:
        existing = db().table("drafts").select("id").eq(
            "transcript_id", t["id"]
        ).limit(1).execute().data
        if not existing:
            target_t = t
            break
    if not target_t:
        _log.log("nothing_to_repurpose")
        return

    base = datetime.now(timezone.utc)
    text = target_t.get("cleaned_text") or target_t.get("raw_text") or ""
    drafts: list[dict] = []

    for platform, format_, pillar, count in TARGETS:
        for i in range(count):
            body, extra_md = _generate(text, platform, format_, pillar, i)
            if not body:
                continue
            ok, issues = brand_voice.passes_qa(body)
            actual_pillar = classify(body) if pillar == "both" else pillar
            md = {**extra_md, **({"qa_issues": issues} if not ok else {})}
            drafts.append({
                "transcript_id": target_t["id"],
                "platform": platform, "format": format_, "pillar": actual_pillar,
                "body": body,
                "metadata": md,
                "scheduled_for": assign(platform, format_, actual_pillar, i, base).isoformat(),
                "status": "pending",
            })

    _reslot_linkedin(drafts, base)
    if drafts:
        db().table("drafts").insert(drafts).execute()
    _log.log("repurpose_done",
             metadata={"transcript_id": target_t["id"], "drafts": len(drafts)})


async def repurpose_from_ideas(max_ideas: int = 3) -> None:
    """Generate drafts directly from queued ideas — no transcript required.

    Pulls top-priority pending ideas, uses each as the seed for one
    LinkedIn post per idea. Marks ideas as 'used' on success.
    """
    from ..idea_queue import store as idea_store

    ideas = idea_store.pending_ideas(limit=max_ideas)
    if not ideas:
        _log.log("no_pending_ideas")
        return

    base = datetime.now(timezone.utc)
    drafts: list[dict] = []

    # Per-idea fan-out — every idea generates 5 pieces: LinkedIn post,
    # LinkedIn article, Substack post, Medium article, Newsletter section.
    # Long-form (article/section/substack-post) runs through the editorial
    # 3-stage pipeline; LinkedIn posts are single-shot.
    # Sunset: Medium/Substack dropped; LinkedIn posts + article + newsletter are
    # all owned by voices_daily. Nothing to fan out per idea here anymore —
    # ideas remain in the queue as ai_guy source material.
    PER_IDEA: list[tuple[str, str, str, int]] = []

    used_ids: list[str] = []
    for idea in ideas:
        seed_text = idea["content"]
        parsed = idea.get("parsed_content") or {}
        if parsed.get("transcript"):
            seed_text = f"{seed_text}\n\nReference transcript:\n{parsed['transcript'][:6000]}"
        elif parsed.get("body"):
            seed_text = f"{seed_text}\n\nReference page content:\n{parsed['body'][:6000]}"

        produced_any = False
        for platform, format_, pillar, count in PER_IDEA:
            for i in range(count):
                body, extra_md = _generate(seed_text, platform, format_, pillar, i)
                if not body:
                    continue
                ok, issues = brand_voice.passes_qa(body)
                actual_pillar = classify(body) if pillar == "both" else pillar
                drafts.append({
                    "platform": platform, "format": format_, "pillar": actual_pillar,
                    "body": body,
                    "metadata": {
                        "idea_id": idea["id"],
                        "idea_source": idea["source"],
                        **extra_md,
                        **({"qa_issues": issues} if not ok else {}),
                    },
                    "scheduled_for": assign(platform, format_, actual_pillar, i, base).isoformat(),
                    "status": "pending",
                })
                produced_any = True
        if produced_any:
            used_ids.append(idea["id"])

    _reslot_linkedin(drafts, base)
    if drafts:
        db().table("drafts").insert(drafts).execute()
    for idea_id in used_ids:
        idea_store.mark_used(idea_id)
    _log.log("repurpose_from_ideas_done",
             metadata={"ideas_used": len(used_ids), "drafts": len(drafts)})


async def use_now_drain() -> None:
    """Immediate-fire path for the dashboard 'Use Now' button.

    Fires every 2 min via cron. Looks for content_ideas rows that have
    metadata.use_now_requested_at set and runs the same PER_IDEA fan-out
    as repurpose_from_ideas, but only for those flagged ideas. Limits to 5
    ideas per tick so a flurry of clicks doesn't blow up token cost.
    """
    from ..idea_queue import store as idea_store

    ideas = idea_store.use_now_pending(limit=5)
    if not ideas:
        return

    _log.log("use_now_start", metadata={"count": len(ideas)})
    base = datetime.now(timezone.utc)
    drafts: list[dict] = []

    # Use Now keeps an on-demand LinkedIn 'post' (tagged ai_guy) so the dashboard
    # button still fires an immediate LinkedIn draft. Medium/Substack sunset;
    # newsletter + article are owned by voices_daily.
    PER_IDEA: list[tuple[str, str, str, int]] = [
        ("linkedin",   "post",    "1",    1),
    ]

    used_ids: list[str] = []
    for idea in ideas:
        seed_text = idea["content"]
        parsed = idea.get("parsed_content") or {}
        if parsed.get("transcript"):
            seed_text = f"{seed_text}\n\nReference transcript:\n{parsed['transcript'][:6000]}"
        elif parsed.get("body"):
            seed_text = f"{seed_text}\n\nReference page content:\n{parsed['body'][:6000]}"

        produced_any = False
        for platform, format_, pillar, count in PER_IDEA:
            for i in range(count):
                body, extra_md = _generate(seed_text, platform, format_, pillar, i)
                if not body:
                    continue
                ok, issues = brand_voice.passes_qa(body)
                actual_pillar = classify(body) if pillar == "both" else pillar
                drafts.append({
                    "platform": platform, "format": format_, "pillar": actual_pillar,
                    "body": body,
                    "metadata": {
                        "idea_id": idea["id"],
                        "idea_source": idea["source"],
                        "via_use_now": True,
                        **({"voice": "ai_guy"} if platform == "linkedin" else {}),
                        **extra_md,
                        **({"qa_issues": issues} if not ok else {}),
                    },
                    "scheduled_for": assign(platform, format_, actual_pillar, i, base).isoformat(),
                    "status": "pending",
                })
                produced_any = True
        if produced_any:
            used_ids.append(idea["id"])

    _reslot_linkedin(drafts, base)
    if drafts:
        db().table("drafts").insert(drafts).execute()
    for idea_id in used_ids:
        idea_store.mark_used(idea_id)
    _log.log("use_now_done", metadata={
        "ideas_used": len(used_ids), "drafts": len(drafts),
    })


async def auto_tune_voice() -> None:
    """Sunday — log which approved/published posts should promote into FEW_SHOT_*."""
    cutoff = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    candidates = db().table("drafts").select("*").in_(
        "status", ["approved", "edited", "published"]
    ).order("published_at", desc=True).limit(50).execute().data or []
    _log.log("auto_tune_candidates",
             metadata={"count": len(candidates), "as_of": cutoff})


async def run() -> None:
    return
