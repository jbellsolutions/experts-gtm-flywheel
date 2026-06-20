"""Browser-runner — consumes Redis browser-job queue, runs Browser Use Cloud.

Engine: Browser Use Cloud (super-browser Tier 1). The runner no longer ships
a local Chromium — sessions run in BU's hardened cloud Chromium under a
per-platform persistent profile.

Profiles are captured ONCE in the BU dashboard (cloud.browser-use.com) and
referenced here by ID via env vars:
  - BU_PROFILE_SUBSTACK
  - BU_PROFILE_MEDIUM
  - BU_PROFILE_TWITTER
  - BU_PROFILE_FACEBOOK   (set when the FB login is captured; until then,
                           FB jobs fail-fast with a clear error)

For each job:
  1. Look up profile_id for the platform from env.
  2. Create a BU Cloud session bound to that profile.
  3. Run the platform-specific natural-language task; force structured output
     so success URL extraction is deterministic (no more "returned no URL").
  4. Update drafts.status='published' + publish_url, OR status='failed' + Slack.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from shared.db import db
from shared.logging.logger import AgentLogger
from shared.notifications.slack import SlackNotifier
from shared.redis_queue import dequeue, BROWSER_QUEUE

_log = AgentLogger("browser-runner")


# ── Browser Use Cloud config ────────────────────────────────────────────────
_BU_API_KEY = os.getenv("BROWSER_USE_API_KEY", "")
_BU_MODEL = os.getenv("BROWSER_USE_MODEL", "claude-sonnet-4.6")

# Platform -> profile_id (BU Cloud profile UUIDs). Set in Railway env vars.
# Each value is the UUID returned by cloud.browser-use.com after capturing
# a login session for that platform. Missing profile -> job fails fast.
_PROFILE_ENV = {
    "substack": "BU_PROFILE_SUBSTACK",
    "medium":   "BU_PROFILE_MEDIUM",
    "linkedin": "BU_PROFILE_LINKEDIN",  # used for group scans; publishing is Unipile
}


def _profile_for(platform: str) -> str | None:
    """Return the BU Cloud profile_id for a given platform, or None."""
    env_name = _PROFILE_ENV.get(platform)
    if not env_name:
        return None
    return os.getenv(env_name) or None


class PublishResult(BaseModel):
    """Structured result the BU agent must return after a publish task.

    Forcing structured output via output_schema fixes the prior failure mode
    where the agent ran successfully but its free-text response didn't
    contain a parseable URL.
    """
    posted: bool = Field(description="True iff the post was actually published")
    url: str | None = Field(default=None, description="Canonical URL of the published post")
    error: str | None = Field(default=None, description="Error if posted=False")


PUBLISH_TASKS = {
    "substack": (
        "You are creating a Substack post for me. "
        "Navigate to {publication_url}/publish/post?type=newsletter (you may already be there). "
        "Type the title: {title!r}. "
        "Tab into the body editor and type the body content. "
        "{action_clause} "
        "After completion, return the canonical URL of the post "
        "(the editor URL is fine if it's only saved as a draft)."
    ),
    "medium": (
        "You are creating a Medium article. "
        "Go to https://medium.com/new-story. "
        "Type the title (first line, big): {title!r}. "
        "Press Enter, then type the body content. "
        "{action_clause} "
        "After completion, return the canonical URL of the article."
    ),
    "linkedin_article": (
        "You are publishing a LinkedIn article for me (I am already logged in). "
        "Go to https://www.linkedin.com/article/new/. "
        "If asked where to publish, choose a standalone article (NOT a newsletter). "
        "Type the headline: {title!r}. "
        "Click into the article body and type the content. "
        "{action_clause} "
        "After completion, return the canonical URL of the published article."
    ),
    "linkedin_newsletter": (
        "You are publishing a new edition of my existing LinkedIn newsletter "
        "(I am already logged in). "
        "Go to https://www.linkedin.com/article/new/. "
        "If asked where to publish, SELECT my existing newsletter (publish as a "
        "newsletter edition, not a standalone article). "
        "Type the edition title: {title!r}. "
        "Click into the body and type the content. "
        "{action_clause} "
        "After completion, return the canonical URL of the published edition."
    ),
}


def _browser_session_platform(job_platform: str) -> str:
    """Map a job platform/kind to the auth profile that holds the login."""
    if job_platform in ("linkedin_article", "linkedin_newsletter"):
        return "linkedin"
    return job_platform


_bu_client = None


def _client():
    """Lazy, cached Browser Use Cloud v3 client."""
    global _bu_client
    if _bu_client is not None:
        return _bu_client
    if not _BU_API_KEY:
        raise RuntimeError("BROWSER_USE_API_KEY not set — cannot run browser jobs")
    try:
        from browser_use_sdk.v3 import BrowserUse  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "browser-use-sdk not installed (pip install browser-use-sdk)"
        ) from e
    _bu_client = BrowserUse(api_key=_BU_API_KEY)
    return _bu_client


def _run_bu_sync(task: str, profile_id: str, output_schema=None) -> object:
    """Synchronous BU Cloud v3 invocation. Run inside asyncio.to_thread().

    Returns a SessionResult — access .output for the parsed schema instance
    (when output_schema is set) or the raw string output otherwise.
    """
    client = _client()
    kwargs = {"task": task, "profile_id": profile_id, "model": _BU_MODEL}
    if output_schema is not None:
        kwargs["schema"] = output_schema
    return client.run(**kwargs)


async def _run_browser_use(task: str, platform: str,
                           output_schema=None) -> object | None:
    """Drive a BU Cloud session under the profile for `platform`.

    Returns whatever the SDK returns (a Pydantic object if output_schema is
    set, otherwise free text). Caller is responsible for shape handling.
    Returns None on hard failure (no profile, no key, SDK import error).
    """
    profile_id = _profile_for(platform)
    if not profile_id:
        _log.error(
            "no_profile",
            f"no BU profile for {platform!r}. Set "
            f"{_PROFILE_ENV.get(platform, 'BU_PROFILE_<PLATFORM>')} in Railway "
            f"after capturing the login at cloud.browser-use.com.",
        )
        return None
    try:
        return await asyncio.to_thread(_run_bu_sync, task, profile_id, output_schema)
    except Exception as e:
        _log.error("bu_run_failed", str(e),
                   metadata={"platform": platform, "profile_id": profile_id[:8] + "..."})
        return None


async def _publish_via_browser_use(job: dict) -> str | None:
    """Publish a draft via Browser Use Cloud. Returns published URL or None."""
    template = PUBLISH_TASKS.get(job["platform"])
    if not template:
        _log.error("unknown_platform", job["platform"])
        return None

    # dry_run=true => save as draft inside the platform; don't broadcast.
    # Used for smoke tests so we can verify the BU pipeline without spamming.
    dry_run = bool(job.get("dry_run"))
    platform = job["platform"]
    if dry_run:
        action_clause = (
            "DO NOT publish or broadcast. Save it as a draft only — "
            "click 'Save Draft' (or the equivalent draft-save button) and stop."
        )
    elif platform == "substack":
        action_clause = (
            "Click Continue, then Send to All Subscribers (or Publish). "
            "Confirm any modal."
        )
    elif platform == "medium":
        action_clause = (
            "Click Publish in the top-right, then 'Publish now' in the modal."
        )
    elif platform in ("linkedin_article", "linkedin_newsletter"):
        action_clause = (
            "Click Publish (top right). If a settings panel appears, leave the "
            "defaults and confirm Publish. Dismiss any 'share to feed' modal."
        )
    else:
        action_clause = "Click Publish and confirm any modal."

    instruction = template.format(
        publication_url=job.get("publication_url", ""),
        title=job.get("title", ""),
        group_url=job.get("group_url", ""),
        action_clause=action_clause,
    ) + (
        f"\n\nBODY TO POST:\n{job['body']}\n\n"
        "When done, return a JSON object with keys "
        "{posted: bool, url: str | null, error: str | null}. "
        "url MUST be the canonical published URL when posted=true."
    )

    result = await _run_browser_use(
        instruction,
        _browser_session_platform(job["platform"]),
        output_schema=PublishResult,
    )
    if result is None:
        return None
    # v3 SDK returns a SessionResult with .output as the parsed Pydantic.
    parsed: PublishResult | None = None
    candidate = getattr(result, "output", result)
    if isinstance(candidate, PublishResult):
        parsed = candidate
    elif isinstance(candidate, dict):
        try:
            parsed = PublishResult(**candidate)
        except Exception:
            parsed = None
    if parsed is None:
        _log.error("publish_result_unparseable", repr(result)[:200],
                   metadata={"platform": job["platform"]})
        return None
    if not parsed.posted:
        _log.error("publish_not_posted", parsed.error or "unknown",
                   metadata={"platform": job["platform"]})
        return None
    return parsed.url


async def _process(job: dict) -> None:
    draft_id = job.get("draft_id")
    _log.log("job_start", metadata={"platform": job.get("platform"), "draft_id": draft_id})

    try:
        url = await _publish_via_browser_use(job)
        if url:
            db().table("drafts").update({
                "status": "published",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "publish_url": url,
            }).eq("id", draft_id).execute()
            _log.log("published", metadata={"draft_id": draft_id, "url": url})
        else:
            raise RuntimeError("browser_use returned no URL")
    except Exception as e:
        db().table("drafts").update({
            "status": "failed",
            "metadata": {"error": str(e)},
        }).eq("id", draft_id).execute()
        _log.error("publish_failed", str(e),
                   metadata={"draft_id": draft_id, "platform": job.get("platform")})
        try:
            await SlackNotifier().send(
                "ops", f":warning: browser publish failed for {job.get('platform')} "
                       f"draft {draft_id}: {e}", "browser-runner", priority="high")
        except Exception:
            pass


async def main_loop() -> None:
    """Long-running consumer — Railway runs this as the browser-runner service entrypoint."""
    _log.log("browser_runner_start", metadata={
        "engine": "browser_use_cloud",
        "model": _BU_MODEL,
        "profiles": {k: bool(_profile_for(k)) for k in _PROFILE_ENV},
    })
    while True:
        try:
            job = dequeue(BROWSER_QUEUE, timeout=30)
        except Exception as e:
            # Redis socket timeouts (the BRPOP polling cadence) used to crash
            # the consumer; now we just log and re-loop. Real errors are still
            # surfaced via structured logging.
            _log.log("dequeue_retry", metadata={"err": str(e)[:160]})
            await asyncio.sleep(5)
            continue
        if not job:
            continue
        try:
            await _process(job)
        except Exception as e:
            _log.error("loop_error", str(e))


async def login_flow(platform: str) -> str:
    """Profile capture now happens in the Browser Use Cloud dashboard.

    Operator workflow:
      1. Go to https://cloud.browser-use.com → Profiles
      2. Create / open the profile for `platform` (Substack, Medium, etc.)
      3. Launch the browser, log into the target site, close the window
      4. Copy the profile_id and set the matching env var in Railway:
         BU_PROFILE_SUBSTACK, BU_PROFILE_MEDIUM, BU_PROFILE_TWITTER, etc.

    The browser-runner reloads its env on the next deploy.
    """
    env_name = _PROFILE_ENV.get(platform, "BU_PROFILE_<PLATFORM>")
    return (
        f"Capture {platform} login in the Browser Use Cloud dashboard "
        f"(https://cloud.browser-use.com) and set {env_name} in Railway."
    )


if __name__ == "__main__":
    asyncio.run(main_loop())
