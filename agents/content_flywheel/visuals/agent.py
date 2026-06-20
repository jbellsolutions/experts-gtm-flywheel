"""Visual layer — gives every LinkedIn post ONE visual: carousel, image, or video.

Decoupled crons:
- generate_pending(): finds pending LinkedIn 'post' drafts with no visual, asks
  the editorial orchestrator to pick carousel | image | video (+ justify),
  generates the copy in your voice, renders the brand SVG templates to PNG
  (optionally on a HiggsField hero), uploads to Supabase Storage, and stamps
  `metadata.visual`. Video is async: it stamps status="generating" + a job_id.
- resolve_pending_videos(): polls those async video jobs; when a clip finishes
  it composites the crisp brand text overlay on with ffmpeg, uploads the mp4,
  and flips status to "rendered". A failed/slow job degrades to the static hero
  card that was already rendered — a HiggsField hiccup never blocks a post.

Failures stamp `metadata.visual_error` so the cron doesn't retry forever.
"""
from __future__ import annotations

from datetime import datetime, timezone

from shared.db import db
from shared.logging.logger import AgentLogger

from . import copy, hero, higgs, motion, render, storage, variant

_log = AgentLogger("visuals")

# Give up on a video job still "generating" after this long and fall back to the
# static card, so a stuck job never strands a post without a visual.
VIDEO_MAX_AGE_MIN = 25


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _age_min(iso: str | None) -> float:
    try:
        t = datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t).total_seconds() / 60.0
    except Exception:  # noqa: BLE001
        return 0.0


async def generate_pending() -> None:
    """Cron entrypoint — fill visuals for pending LinkedIn posts + the Kit
    newsletter (platform='newsletter', format='section') that lack one. Long-form
    formats (article / newsletter / section) get a single branded cover image."""
    rows = (db().table("drafts")
            .select("id,body,pillar,metadata,status,format,platform")
            .in_("platform", ["linkedin", "newsletter"])
            .in_("format", ["post", "article", "newsletter", "section"])
            .in_("status", ["pending", "approved", "edited"])
            .is_("published_at", "null")
            .limit(25).execute().data or [])
    todo = [r for r in rows
            if not (r.get("metadata") or {}).get("visual")
            and not (r.get("metadata") or {}).get("visual_error")]
    _log.log("visuals_scan", metadata={"pending": len(rows), "to_fill": len(todo)})
    if not todo:
        return
    storage.ensure_bucket()
    for r in todo:
        try:
            _fill_visual(r)
        except Exception as e:
            md = {**(r.get("metadata") or {}),
                  "visual_error": str(e)[:400], "visual_error_at": _now()}
            db().table("drafts").update({"metadata": md}).eq("id", r["id"]).execute()
            _log.error("visual_failed", str(e), metadata={"draft_id": r["id"]})


def _make_hero(body: str) -> tuple[bytes | None, dict | None, str]:
    """Generate a HiggsField hero (best-effort). Returns (png, meta, scene)."""
    if not hero.is_enabled():
        return None, None, ""
    try:
        scene = copy.hero_prompt(body)
        png = hero.hero_for(scene)
        meta = ({"engine": "higgsfield", "model": hero.HERO_MODEL, "scene": scene}
                if png else None)
        return png, meta, scene
    except Exception as e:  # noqa: BLE001
        _log.error("hero_failed", str(e))
        return None, None, ""


def _fill_visual(draft: dict) -> None:
    body = draft.get("body") or ""
    pillar = draft.get("pillar") or "1"
    did = draft["id"]

    # Manual override: metadata.force_visual ∈ {carousel,image,video} skips the
    # orchestrator (dashboard control + deterministic testing). force_mode picks
    # the video mode. Video force is ignored when video isn't enabled.
    # Long-form (LinkedIn article / newsletter) gets a single branded hero cover
    # image — no carousel/video orchestration.
    force = (draft.get("metadata") or {}).get("force_visual")
    if (draft.get("format") or "post") != "post":
        decision = {"format": "image", "reason": "cover image for long-form"}
    elif force in ("carousel", "image", "video"):
        if force == "video" and not motion.is_enabled():
            decision = {"format": "image",
                        "reason": "force_visual=video but video is disabled — using image."}
        elif force == "video":
            decision = {"format": "video",
                        "mode": (draft.get("metadata") or {}).get("force_mode") or "motion",
                        "reason": "Manually forced to video.",
                        "motion_reason": "manual override (force_visual)"}
        else:
            decision = {"format": force, "reason": f"Manually forced to {force}."}
    else:
        decision = copy.decide_visual(body, allow_video=motion.is_enabled())
    fmt = decision["format"]
    reason = decision["reason"]

    # Art-director step: rotate the look so consecutive posts never share one
    # (palette / gradient angle / bg treatment / composition). Picked ONCE per
    # draft so a carousel's slides stay internally consistent.
    var = variant.pick()
    base = {"format_reason": reason, "decided_by": "editorial_orchestrator",
            "variant": var["key"]}

    if fmt == "carousel":
        slides = copy.carousel_copy(body, pillar)
        if len(slides) < 3:              # weak/short copy → single card instead
            fmt = "image"
            reason = (reason + " (fell back to a single card — not enough distinct "
                      "slides).").strip()
            base["format_reason"] = reason
        else:
            pngs = render.render_carousel(slides, variant=var)
            urls = [storage.upload_png(f"post-visuals/{did}/slide-{i+1:02d}.png", p)
                    for i, p in enumerate(pngs)]
            visual = {"type": "carousel", "status": "rendered", "engine": "cairosvg",
                      "hero": None, "rendered_at": _now(),
                      "slide_urls": urls, "slide_copy": slides, **base}
            _commit(draft, visual, reason)
            return

    if fmt == "video":
        _fill_video(draft, body, pillar, decision, base, var)
        return

    # image (default / fallback)
    card = copy.image_copy(body, pillar)
    hero_png, hero_meta, _ = _make_hero(body)
    png = render.render_image(card, hero=hero_png, variant=var)
    url = storage.upload_png(f"post-visuals/{did}/card.png", png)
    visual = {"type": "image", "status": "rendered", "engine": "cairosvg",
              "hero": hero_meta, "rendered_at": _now(),
              "image_url": url, "card_copy": card, **base}
    _commit(draft, visual, reason)


def _fill_video(draft: dict, body: str, pillar: str, decision: dict, base: dict,
                var: dict | None = None) -> None:
    """Render the static anchor card + overlay, then kick off an async motion job.

    Always uploads the static hero card first — that's the guaranteed fallback if
    the video job fails or runs long. Stamps status="generating"; the resolver
    cron finishes it.
    """
    did = draft["id"]
    mode = decision.get("mode") or "motion"
    card = copy.image_copy(body, pillar)
    hero_png, hero_meta, scene = _make_hero(body)

    # Static anchor card (fallback) + transparent text overlay (for ffmpeg).
    anchor_png = render.render_image(card, hero=hero_png, variant=var)
    anchor_url = storage.upload_png(f"post-visuals/{did}/anchor.png", anchor_png)
    overlay_png = render.render_overlay(card, variant=var)
    overlay_url = storage.upload_png(f"post-visuals/{did}/overlay.png", overlay_png)

    # motion mode needs a clean (text-free) hero to animate; without one, do
    # concept (text->video) instead, else fall back to the static card.
    job_id = None
    if mode == "concept":
        job_id = motion.start("concept", scene=scene)
        model = motion.CONCEPT_MODEL
    elif hero_png:
        job_id = motion.start("motion", image=hero_png, scene=scene)
        model = motion.MOTION_MODEL
    else:
        model = None

    if not job_id:
        # couldn't start a job → ship the static hero card now. Capture WHY
        # (the CLI error) so we can diagnose without scraping container logs.
        note = " (video unavailable — shipped the static card)."
        visual = {"type": "image", "status": "rendered", "engine": "cairosvg",
                  "hero": hero_meta, "rendered_at": _now(),
                  "image_url": anchor_url, "card_copy": card,
                  "video_error": higgs.LAST_ERROR,
                  **{**base, "format_reason": (base["format_reason"] + note).strip()}}
        _commit(draft, visual, visual["format_reason"])
        return

    visual = {"type": "video", "status": "generating", "mode": mode,
              "engine": "higgsfield+ffmpeg", "model": model, "job_id": job_id,
              "hero": hero_meta, "anchor_image_url": anchor_url,
              "overlay_url": overlay_url, "card_copy": card,
              "motion_reason": decision.get("motion_reason", ""),
              "started_at": _now(), **base}
    _commit(draft, visual, base["format_reason"])
    _log.log("video_started", metadata={"draft_id": did, "mode": mode, "job_id": job_id})


def _commit(draft: dict, visual: dict, reason: str) -> None:
    did = draft["id"]
    md = {**(draft.get("metadata") or {}), "visual": visual}
    md.pop("visual_error", None)
    md.pop("visual_error_at", None)
    db().table("drafts").update({"metadata": md}).eq("id", did).execute()
    _log.log("visual_rendered", metadata={
        "draft_id": did, "type": visual["type"], "status": visual["status"],
        "count": len(visual.get("slide_urls") or [1]), "reason": (reason or "")[:200]})


async def resolve_pending_videos() -> None:
    """Cron entrypoint — finish async video jobs (poll → compose → upload)."""
    rows = (db().table("drafts")
            .select("id,metadata,status")
            .eq("platform", "linkedin").eq("format", "post")
            .is_("published_at", "null")
            .limit(25).execute().data or [])
    todo = [r for r in rows
            if ((r.get("metadata") or {}).get("visual") or {}).get("type") == "video"
            and ((r.get("metadata") or {}).get("visual") or {}).get("status") == "generating"]
    if not todo:
        return
    _log.log("video_resolve_scan", metadata={"generating": len(todo)})
    for r in todo:
        try:
            _resolve_one(r)
        except Exception as e:  # noqa: BLE001
            _log.error("video_resolve_failed", str(e), metadata={"draft_id": r["id"]})


def _resolve_one(draft: dict) -> None:
    did = draft["id"]
    md = draft.get("metadata") or {}
    visual = md.get("visual") or {}
    job_id = visual.get("job_id")

    status, mp4 = motion.resolve(job_id) if job_id else ("unknown", None)

    if status == "completed" and mp4:
        overlay = higgs.download(visual.get("overlay_url") or "") if visual.get("overlay_url") else None
        final = motion.compose(mp4, overlay) if overlay else mp4
        if final:
            vurl = storage.upload_mp4(f"post-visuals/{did}/motion.mp4", final)
            visual.update(status="rendered", video_url=vurl, resolved_at=_now())
            _save(did, md, visual)
            _log.log("video_rendered", metadata={"draft_id": did, "url": vurl[:90]})
            return
        # compose failed → fall through to static fallback below
        status = "failed"

    if status in ("failed", "error", "canceled") or _age_min(visual.get("started_at")) > VIDEO_MAX_AGE_MIN:
        # Degrade to the static hero card we already rendered.
        visual.update(type="image", status="rendered",
                      image_url=visual.get("anchor_image_url"),
                      video_error=f"job {status}", resolved_at=_now())
        _save(did, md, visual)
        _log.log("video_fallback_static", metadata={"draft_id": did, "why": status})
    # else still in_progress → leave it for the next tick


def _save(did: str, md: dict, visual: dict) -> None:
    md = {**md, "visual": visual}
    db().table("drafts").update({"metadata": md}).eq("id", did).execute()


if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_pending())
