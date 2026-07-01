"""Content flywheel cron registrations.

Imported by workflows/scheduler.py. Each entry is (cron_expr, callable).
Callables are async and import their agent module lazily so the scheduler
can boot even if a sub-agent has missing config.
"""
from __future__ import annotations

import importlib
from typing import Awaitable, Callable

CronJob = tuple[str, Callable[[], Awaitable[None]]]


def _lazy(module_path: str, fn_name: str) -> Callable[[], Awaitable[None]]:
    async def _run() -> None:
        module = importlib.import_module(module_path)
        await getattr(module, fn_name)()
    _run.__name__ = f"{module_path}.{fn_name}"
    return _run


JOBS: list[CronJob] = [
    # Tue/Thu 22:00 — pull the day's YouTube live transcript
    ("0 22 * * 2,4", _lazy("agents.content_flywheel.transcript_ingest.agent", "ingest_latest")),

    # Tue/Thu 22:30 — generate the week's drafts from that transcript
    ("30 22 * * 2,4", _lazy("agents.content_flywheel.repurposer.agent", "repurpose_latest")),

    # Daily 05:00 ET (09:00 UTC) — generate today's checklist + Slack DM
    ("0 9 * * *", _lazy("agents.content_flywheel.daily_checklist.agent", "generate_today")),

    # Daily 06:00 ET (10:00 UTC) — broader morning summary (kept as a backup ping)
    ("0 10 * * *", _lazy("agents.content_flywheel.review_queue.agent", "assemble_morning_batch")),

    # Publish windows (UTC → ET, EDT): 11:00=7am, 12:00=8am, 16:00=12pm,
    # 18:00=2pm, 19:00=3pm, 21:00=5pm. The 8am + 2pm windows were added so the
    # two daily flagship posts publish at the times you set (your brand 8am ET,
    # POV voice 2pm ET — see VOICE_SLOT). Newsletter/article schedule times were
    # nudged so they still land in the 12pm/3pm windows, not the new ones.
    # — publish whatever's approved & due.
    ("0 11,12,16,18,19,21 * * *", _lazy("agents.content_flywheel.publisher.agent", "publish_due")),

    # Friday 21:00 UTC = 5pm ET — weekly analytics digest to Slack
    ("0 21 * * 5", _lazy("agents.content_flywheel.review_queue.agent", "weekly_digest")),

    # Sunday 03:00 — auto-tune brand voice from approved/edited diffs
    ("0 3 * * 0", _lazy("agents.content_flywheel.repurposer.agent", "auto_tune_voice")),

    # Friday 18:00 UTC (1pm ET) — pull engagement stats for last 30 days of posts
    ("0 18 * * 5", _lazy("agents.content_flywheel.metrics.agent", "fetch_all")),

    # ── Content idea queue ────────────────────────────────────────────
    # Every 2 min — poll your Slack DMs to the bot for new ideas
    ("*/2 * * * *", _lazy("agents.content_flywheel.idea_queue.slack_poller", "poll")),

    # Daily 04:00 ET (08:00 UTC) — pull AI/automation trends from HN + Reddit
    ("0 8 * * *", _lazy("agents.content_flywheel.idea_queue.trends_scraper", "scrape")),

    # Every 6 hours — if queue is low (<5 pending), generate brand-voice ideas
    ("0 */6 * * *", _lazy("agents.content_flywheel.idea_queue.suggester", "maybe_suggest")),

    # Daily 21:00 UTC (off-cycle from Tue/Thu transcripts) — burn through ideas
    # on days when there's no fresh transcript to repurpose from.
    ("0 21 * * 0,1,3,5,6", _lazy("agents.content_flywheel.repurposer.agent", "repurpose_from_ideas")),

    # Daily 23:30 UTC — the three-voice LinkedIn engine: build tomorrow's 3 posts,
    # one per voice (ai_guy morning, human_loop midday, ai_reality mid-afternoon),
    # each = voice × current trend × industry use case. Morning approval window.
    ("30 23 * * *", _lazy("agents.content_flywheel.repurposer.voices_daily", "generate_daily_voices")),
    # Every 2 min — regenerate any draft the dashboard "Rerun" button flagged.
    ("*/2 * * * *", _lazy("agents.content_flywheel.repurposer.voices_daily", "rerun_drain")),

    # Every 2 min — drain ideas flagged by the dashboard "Use Now" button.
    # Generates 1 LinkedIn + 1 Substack + 1 Medium draft per flagged idea
    # immediately, instead of waiting for the off-cycle 21:00 UTC schedule.
    ("*/2 * * * *", _lazy("agents.content_flywheel.repurposer.agent", "use_now_drain")),

    # Every 5 min — give each pending LinkedIn post a visual (carousel, image, or
    # video), rendered to brand SVG templates and stored for preview + publish.
    ("*/5 * * * *", _lazy("agents.content_flywheel.visuals.agent", "generate_pending")),
    # Every 3 min — finish async HiggsField motion-video jobs (poll → ffmpeg
    # compose brand text overlay → upload mp4 → flip status to rendered).
    ("*/3 * * * *", _lazy("agents.content_flywheel.visuals.agent", "resolve_pending_videos")),

    # ── Influencer system ─────────────────────────────────────────────
    # Daily 5am UTC — Firecrawl-powered real-world discovery:
    # search Google's index for AI/Anthropic/Claude LinkedIn profiles,
    # LLM-score for authority signal, insert top candidates. Zero LinkedIn touch.
    ("0 5 * * *", _lazy("agents.content_flywheel.influencers.discovery_firecrawl", "discover_real")),

    # Daily 6am UTC — surface 5 LinkedIn people to engage with today.
    ("0 6 * * *", _lazy("agents.content_flywheel.influencers.daily_brief", "send")),

    # Daily 07:00 UTC — find LinkedIn posts to comment on (Firecrawl, zero
    # LinkedIn touch). Drafts a comment in your voice for each; they land
    # on the dashboard Comments tab. Targets ~25/run from tracked influencers +
    # AI keywords.
    ("0 7 * * *", _lazy("agents.content_flywheel.influencers.comment_finder", "find_targets")),

    # Influencer post-tracker disabled Jun 2026 — it called Unipile against
    # your LinkedIn for each tracked person. you asked to NOT touch his
    # LinkedIn account. The daily brief now surfaces "5 people to engage with
    # today" with profile links, and you browses their feeds in his real
    # browser to comment naturally — zero automation footprint on his account.
    # ("0 */4 * * *", _lazy("agents.content_flywheel.influencers.tracker", "fetch_recent")),

    # NOTE: standalone influencer/group briefs are disabled — the daily_checklist
    # at 09:00 UTC (5am ET) folds them into the single morning Slack DM.
    # Leaving the agent functions in place for manual /run.

    # ── Lead-gen pipeline ─────────────────────────────────────────────
    # Every 2 min — drain on-demand lead-gen crawls queued from the dashboard
    # "Crawl selected" button. Each job: pull each influencer's top posts
    # (>=10 comments, last 3mo) via ScrapeCreators, scrape commenters, dedupe,
    # free pre-filter, fetch headline + ICP-score survivors, enrich the fits
    # (email/phone via Bright Data). Credits logged per job; nothing auto-spends.
    ("*/2 * * * *", _lazy("agents.content_flywheel.leadgen.pipeline", "drain_jobs")),
    # Every 3 min — legacy Supabase per-row "Enrich" (kept for any leads still in
    # lead_contacts; the live path is Airtable below).
    ("*/3 * * * *", _lazy("agents.content_flywheel.leadgen.pipeline", "drain_enrich_queue")),
    # Every 3 min — the Airtable CRM: act on Enrich / Create email / Rerun
    # checkboxes on Contacts rows (leads live in Airtable now). No-op until
    # AIRTABLE_API_KEY + AIRTABLE_BASE_ID are set on the worker.
    ("*/3 * * * *", _lazy("agents.content_flywheel.leadgen.pipeline", "drain_airtable")),
    # Every 3 min — auto-qualify newly-scraped Contacts (decision-maker / provider vs
    # prospect / company size) with a cheap Haiku pass, before any paid enrichment.
    ("*/3 * * * *", _lazy("agents.content_flywheel.leadgen.pipeline", "drain_qualify")),
    # Weekly scheduled crawl is built (leadgen.pipeline.run_scheduled) but left
    # OFF until you proves out cost/quality on on-demand batches:
    # ("0 6 * * 1", _lazy("agents.content_flywheel.leadgen.pipeline", "run_scheduled")),
    # (Groups arbitrage removed — the Comments tab covers engagement targets.)
]
