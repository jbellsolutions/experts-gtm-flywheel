"""Optional HiggsField motion video for LinkedIn posts (#1 concept, #2 image->motion).

Two modes the editorial orchestrator can pick (both gated on auth + the
VISUALS_VIDEO_ENABLED flag):

- "motion"  (#2): animate our branded hero card. We image->video the rendered
  *hero* (no text) so the model never warps type, then composite the crisp text
  overlay back on with ffmpeg. Result: a premium branded motion card. Portrait
  is inherited from the 4:5 hero, so no aspect guessing.
- "concept" (#1): text->video concept clip for inherently-visual posts, with the
  same brand text overlay added on top.

Video generation takes MINUTES, so this never blocks the 5-min visuals cron:
`start()` kicks off an async job and returns a job_id; the resolver cron polls
it later (visuals.agent.resolve_pending_videos). Every step degrades cleanly —
a failed/slow job falls back to the static hero card that was already rendered.
"""
from __future__ import annotations

import os
import subprocess
import tempfile

from shared.logging.logger import AgentLogger

from . import higgs

_log = AgentLogger("visuals-motion")

# Models. image->video inherits the input's portrait aspect; text->video gets a
# portrait hint via PARAMS once verified against the live model schema.
MOTION_MODEL = "seedance1_5"     # image -> video (animate the hero)
CONCEPT_MODEL = "veo3_1_lite"    # text  -> video (concept clip)

# Generation params (verified against the live model schema 2026-06-12).
# Both get normalized to 1080x1350 (4:5) by ffmpeg, so we just pick the closest
# portrait the model offers and keep clips short (4s) for LinkedIn + cost.
#   seedance1_5: aspect_ratio∈{auto,16:9,9:16,4:3,3:4,1:1,21:9}, duration∈{4,8,12},
#                resolution∈{480p,720p,1080p}  → 3:4 is closest to our 4:5 hero.
#   veo3_1_lite: aspect_ratio∈{16:9,9:16,auto}, duration∈{4,6,8}  → 9:16 portrait.
# Motion (i2v) inherits aspect/resolution from the input hero, so we keep only
# duration — explicit aspect_ratio can conflict with the supplied image. ffmpeg
# normalizes to 1080x1350 regardless. Concept (t2v) has no input, so it needs an
# explicit portrait aspect.
MOTION_PARAMS: dict = {"duration": "4"}
CONCEPT_PARAMS: dict = {"aspect_ratio": "9:16", "duration": "4", "generate_audio": "false"}

# Brand art-direction for the motion itself (subtle, premium — never frenetic).
_MOTION_DIRECTION = (
    "Subtle premium motion: slow drifting gradient light, gentle parallax depth, "
    "soft particle/energy flow. Dark navy with blue-to-violet glow. Minimal, "
    "high-end, cinematic. No text, no people, no logos."
)
_CONCEPT_DIRECTION = (
    "Abstract conceptual b-roll, dark navy with electric-blue to violet glow, "
    "premium minimal high-end tech aesthetic, slow cinematic motion, no text, "
    "no people, no logos. Concept: {scene}"
)

MAX_CLIP_SECONDS = 12


def is_enabled() -> bool:
    """Video is opt-in: needs HiggsField auth AND the VISUALS_VIDEO_ENABLED flag."""
    flag = (os.getenv("VISUALS_VIDEO_ENABLED") or "").lower() in ("1", "true", "yes", "on")
    return flag and higgs.is_enabled()


def start(mode: str, *, image: bytes | None = None, scene: str = "") -> str | None:
    """Kick off an async video job. Returns a job_id to poll later, or None.

    mode="motion": image->video the supplied hero PNG (no text).
    mode="concept": text->video from the scene motif.
    """
    try:
        if mode == "concept":
            prompt = _CONCEPT_DIRECTION.format(scene=(scene or "abstract data flow").strip()[:240])
            return higgs.create_async(CONCEPT_MODEL, prompt, params=CONCEPT_PARAMS)
        # motion: animate the hero image
        if not image:
            return None
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(image)
            path = f.name
        try:
            return higgs.create_async(MOTION_MODEL, _MOTION_DIRECTION,
                                      image=path, params=MOTION_PARAMS)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    except Exception as e:  # noqa: BLE001
        _log.error("motion_start_failed", str(e), metadata={"mode": mode})
        return None


def resolve(job_id: str) -> tuple[str, bytes | None]:
    """Poll a job. Returns (status, mp4_bytes|None). status: completed|failed|in_progress|unknown."""
    status, urls = higgs.poll(job_id)
    if status == "completed" and urls:
        return "completed", higgs.download(urls[0])
    return status, None


def compose(video: bytes, overlay_png: bytes) -> bytes | None:
    """ffmpeg: fit the clip to 1080x1350 and composite the brand text overlay.

    The overlay is a full-frame transparent PNG, so type stays crisp over the
    moving backdrop. Returns the final mp4 bytes, or None on failure (caller
    falls back to the static card).
    """
    try:
        with tempfile.TemporaryDirectory() as d:
            vin = os.path.join(d, "in.mp4")
            oin = os.path.join(d, "overlay.png")
            vout = os.path.join(d, "out.mp4")
            with open(vin, "wb") as f:
                f.write(video)
            with open(oin, "wb") as f:
                f.write(overlay_png)
            cmd = [
                "ffmpeg", "-y", "-i", vin, "-i", oin,
                "-filter_complex",
                ("[0:v]scale=1080:1350:force_original_aspect_ratio=increase,"
                 "crop=1080:1350,setsar=1[v];[v][1:v]overlay=0:0:format=auto[o]"),
                "-map", "[o]", "-map", "0:a?",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
                "-movflags", "+faststart", "-t", str(MAX_CLIP_SECONDS),
                "-an", vout,
            ]
            p = subprocess.run(cmd, capture_output=True, timeout=180)
            if p.returncode != 0:
                _log.error("ffmpeg_failed", (p.stderr or b"")[:300].decode("utf-8", "replace"))
                return None
            with open(vout, "rb") as f:
                return f.read()
    except Exception as e:  # noqa: BLE001
        _log.error("compose_failed", str(e))
        return None
