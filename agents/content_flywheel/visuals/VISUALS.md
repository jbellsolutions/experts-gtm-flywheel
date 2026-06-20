# Visual layer — carousels, hero images & motion video

Every LinkedIn post gets **one** visual, chosen by an editorial orchestrator and
justified: a **carousel**, a **single branded image** (optionally on a
HiggsField AI hero), or a **motion video**. Built for your organic
`ai-guy-flywheel`; this doc is the handoff spec for mirroring into Tony's
`speakeragent-flywheel`.

> One visual per post — never two. Carousel **or** image **or** video.

---

## Pipeline at a glance

```
generate_pending()  (cron */5)                 resolve_pending_videos() (cron */3)
  ├─ decide_visual()  carousel | image | video    ├─ poll hf job
  │     (Haiku, returns format + reason +          ├─ completed → ffmpeg compose
  │      mode/motion_reason for video)             │     brand text overlay → upload mp4
  ├─ carousel → carousel_copy (Sonnet)             │     → status=rendered
  │     → render_carousel → upload PNGs            └─ failed/slow (>25m) → fall back to
  ├─ image → image_copy (+ HiggsField hero)              the static hero card already up
  │     → render_image(hero) → upload PNG
  └─ video → render anchor card + overlay,
        kick off async hf motion job,
        stamp status="generating" + job_id
```

Everything degrades, never blocks a post:
**video → static hero card → flat navy card → text-only.**

---

## Files (`agents/content_flywheel/visuals/`)

| File | Role |
|------|------|
| `agent.py` | crons `generate_pending()` + `resolve_pending_videos()`, `_fill_visual`, `_fill_video`, `_make_hero` |
| `copy.py` | LLM copy: `decide_visual` (orchestrator), `carousel_copy`, `image_copy`, `hero_prompt` |
| `render.py` | SVG→PNG via cairosvg + Pillow line-fit: `render_carousel`, `render_image(hero)`, `render_overlay` |
| `hero.py` | HiggsField hero backdrop (`hero_for`, Nano Banana Pro, 4:5) |
| `motion.py` | HiggsField video (`start` async, `resolve`, ffmpeg `compose`) |
| `higgs.py` | thin subprocess client over the bundled `hf` Go binary (creds, generate, poll, download) |
| `storage.py` | Supabase Storage `post-media` bucket (png + mp4) |
| `assets/brand/{colors,templates}.py` | brand tokens + SVG builders (`cover/point/cta_slide`, `image_card`, `overlay_card`) |

Publisher: `publisher/linkedin.py` attaches the visual to Unipile (`attachments`
multipart, repeated → multi-image carousel; single mp4 → native video).
Dashboard: `dashboard/components/draft-card.tsx` previews all three + the
orchestrator's reasoning.

## `metadata.visual` shapes

```jsonc
// carousel
{ "type":"carousel","status":"rendered","slide_urls":[...],"slide_copy":[...],
  "format_reason":"...","decided_by":"editorial_orchestrator","engine":"cairosvg" }
// image (optionally on a hero)
{ "type":"image","status":"rendered","image_url":"...","card_copy":{...},
  "hero":{"engine":"higgsfield","model":"nano_banana_2","scene":"..."}, ... }
// video — async; starts as "generating", resolver flips to "rendered"
{ "type":"video","status":"generating","mode":"motion|concept","job_id":"...",
  "anchor_image_url":"...","overlay_url":"...","motion_reason":"...",
  "started_at":"...", ... }   // + on success: "video_url","resolved_at"
                              // on failure: downgraded to type=image (image_url=anchor)
```

---

## HiggsField

CLI is a self-contained Go binary (`hf`, v0.1.40) bundled into the worker image
(`Dockerfile.worker`, downloaded from GitHub releases). It powers:

- **Hero images** (`hero.py`, model `nano_banana_2` "Nano Banana Pro", `4:5`,
  ~2 credits, ~30s). Brand art-direction wrapper guarantees navy + blue→violet,
  no text/people. Composited behind the card under a legibility scrim
  (`templates._frame(bg_data_uri=...)`).
- **Motion video** (`motion.py`):
  - `motion` (#2): image→video the **hero** (`seedance1_5`, ~4 credits), then
    ffmpeg-overlay the crisp text so type never warps. Portrait inherited from
    the 4:5 hero.
  - `concept` (#1): text→video concept clip (`veo3_1_lite`, ~8 credits) + same
    overlay.

### Auth (IMPORTANT — durable setup)
The CLI authenticates **only** via a device-login token pair (access + refresh)
in a credentials file; **there is no static API-key env var**. Refresh tokens
are single-use rotating, so a token materialized from env into an ephemeral
container goes stale on restart.

**Durable fix:** a **Railway volume** mounted at `HIGGSFIELD_CREDENTIALS_PATH`
(`/app/.higgsfield/`). The binary refreshes the token in place and writes it back
to the volume, which survives deploys → stays alive indefinitely (it refreshes
as it generates daily). Seed it once from a fresh `hf auth login`. `higgs.py`
materializes creds from env **only if the file is absent**, so the volume's
self-refreshing token is the source of truth.

To re-seed: `hf auth login` locally → copy the new `~/.config/higgsfield/
credentials.json` onto the worker volume (or set `HIGGSFIELD_TOKEN` +
`HIGGSFIELD_REFRESH_TOKEN` and wipe the volume file once so it re-seeds).

---

## Config / env (worker)

| Var | Purpose |
|-----|---------|
| `HIGGSFIELD_CREDENTIALS_PATH` | creds file path (point at the volume) |
| `HIGGSFIELD_TOKEN` / `HIGGSFIELD_REFRESH_TOKEN` | one-time seed for the volume |
| `VISUALS_VIDEO_ENABLED` | gate for motion video (`1` to let the orchestrator pick video) |

Hero needs only valid HiggsField auth. Video additionally needs
`VISUALS_VIDEO_ENABLED`. Neither set → clean carousel/image, text-only safety.

Models routed via `repurposer/model_config.py`: `visual_format_decision`
(orchestrator), `visual_carousel_copy`, `visual_image_copy`, `visual_hero_prompt`.

## Costs (HiggsField credits)
hero ≈ 2 · motion ≈ 4 · concept ≈ 8. At 3 posts/day, mostly carousel/image with
occasional video, this is a few hundred credits/month.

## Gotchas
- cairosvg does **not** wrap text → copy is pre-wrapped + Pillow-fit (`render._fit`).
- Worker auto-deploy is flaky for code-only pushes → force a deploy (env-var
  nudge / `serviceInstanceDeployV2`). See `[[flywheel-deploy-asymmetry]]`.
- **Deploying restarts the worker** → if HiggsField auth isn't on a volume, the
  in-memory refreshed token is lost and the stale env seed may fail. Put auth on
  a volume before relying on it.
- ffmpeg is already in `Dockerfile.worker`; the overlay PNG is full-frame 1080×1350.

## To finalize (post-auth)
- `motion.MOTION_PARAMS` / `CONCEPT_PARAMS` are intentionally empty (minimal
  flags avoid the CLI's unknown-flag errors). Verify `seedance1_5` / `veo3_1_lite`
  param names live (`hf model get <model>`) and add duration / aspect once known.
- Smoke-test one real video end-to-end before flipping `VISUALS_VIDEO_ENABLED` on.

## Mirroring to Tony
Tony's fork overrides `assets/brand/colors.py` (NAVY/gradient/WORDMARK/HANDLE)
and ships his own fonts; the rest is identical. Copy this `visuals/` package +
the `Dockerfile.worker` HiggsField block + the two crons, set his own HiggsField
auth volume + env, and adjust the art-direction wrappers in `hero.py`/`motion.py`
to his palette.
