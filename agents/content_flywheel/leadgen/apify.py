"""Apify `harvestapi` client — FALLBACK collector (not the default).

ScrapeCreators is primary (owned credits, 1 credit/post). Apify is used only when
ScrapeCreators is unavailable, or when we want commenter headline + email in one
shot. It bills ~$0.002 PER COMMENT, so it is the expensive path at volume.

  * harvestapi/linkedin-profile-posts  -> a profile's recent posts + comment counts
  * harvestapi/linkedin-post-comments  -> commenters (name + URL + headline [+ email])

Uses the run-sync-get-dataset-items endpoint so a single call returns items
directly (subject to Apify's ~5 min sync cap; our per-run caps stay well under).
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from shared.logging.logger import AgentLogger

_log = AgentLogger("leadgen.apify")

_BASE = "https://api.apify.com/v2"
_TIMEOUT = 300


class ApifyError(RuntimeError):
    pass


def configured() -> bool:
    return bool(os.getenv("APIFY_TOKEN"))


def _token() -> str:
    t = os.getenv("APIFY_TOKEN")
    if not t:
        raise ApifyError("APIFY_TOKEN not set")
    return t


def run_actor(actor: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Run an actor synchronously and return its dataset items.

    `actor` uses the username~actor-name form, e.g. 'harvestapi~linkedin-post-comments'.
    """
    actor_path = actor.replace("/", "~")
    url = f"{_BASE}/acts/{actor_path}/run-sync-get-dataset-items"
    with httpx.Client(timeout=_TIMEOUT) as c:
        r = c.post(url, params={"token": _token()}, json=payload)
    if r.status_code >= 300:
        raise ApifyError(f"actor {actor} -> {r.status_code}: {r.text[:200]}")
    data = r.json()
    return data if isinstance(data, list) else (data.get("items") or [])


def _first(d: dict, *keys: str) -> Any:
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return None


def post_comments(post_urls: list[str], max_per_post: int = 50) -> list[dict[str, Any]]:
    """[{name, profile_url, headline, comment_text}] for the given posts."""
    items = run_actor("harvestapi/linkedin-post-comments",
                      {"postUrls": post_urls, "maxResults": max_per_post})
    out: list[dict[str, Any]] = []
    for it in items:
        url = _first(it, "profileUrl", "linkedinUrl", "authorUrl", "url")
        if not url:
            continue
        out.append({
            "name": _first(it, "name", "authorName", "fullName"),
            "profile_url": str(url).split("?")[0].rstrip("/"),
            "headline": _first(it, "headline", "occupation", "position"),
            "comment_text": (_first(it, "commentText", "text", "comment") or "").strip(),
            "email": _first(it, "email"),
        })
    return out


def profile_posts(profile_urls: list[str], since_iso: str | None = None) -> list[dict[str, Any]]:
    """[{profile_url, url, comment_count, posted_at, body}] across the profiles."""
    payload: dict[str, Any] = {"profileUrls": profile_urls}
    if since_iso:
        payload["postedAfter"] = since_iso
    items = run_actor("harvestapi/linkedin-profile-posts", payload)
    out: list[dict[str, Any]] = []
    for it in items:
        u = _first(it, "url", "postUrl", "link")
        if not u:
            continue
        out.append({
            "profile_url": _first(it, "authorProfileUrl", "profileUrl", "author"),
            "url": u,
            "comment_count": _first(it, "commentCount", "numComments", "comments") or 0,
            "posted_at": _first(it, "postedAt", "datePublished", "date"),
            "body": _first(it, "text", "content", "description") or "",
        })
    return out


# ── Validated primary: ALL commenters of a post, no LinkedIn account ──────────
# apimaestro's no-cookies scraper returns every commenter (paginated), vs the BD
# posts dataset / ScrapeCreators which cap at the top ~10. This is the lead source.
COMMENTS_ACTOR = "apimaestro~linkedin-post-comments-replies-engagements-scraper-no-cookies"
_PAGE = 100  # actor page size; also the per-run maxItems cap (pay-per-result guard)


def commenters(post_url: str, max_pages: int = 40) -> list[dict[str, Any]]:
    """Every commenter of a post → [{name, profile_url, comment_text, headline}]."""
    url = f"{_BASE}/acts/{COMMENTS_ACTOR}/run-sync-get-dataset-items"
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        try:
            with httpx.Client(timeout=_TIMEOUT) as c:
                # maxItems is REQUIRED by this pay-per-result actor on a sync run
                # ("Maximum charged results must be greater than zero"). One page
                # worth per call; page_number pagination still walks all commenters.
                r = c.post(url, params={"token": _token(), "maxItems": _PAGE},
                           json={"postIds": [post_url], "page_number": page})
        except Exception as e:  # noqa: BLE001
            _log.error("apify_commenters_failed", str(e), metadata={"page": page})
            break
        if r.status_code >= 300:
            _log.error("apify_commenters_http", f"{r.status_code}: {r.text[:160]}", metadata={"page": page})
            break
        batch = r.json()
        batch = batch if isinstance(batch, list) else (batch.get("items") or [])
        if not batch:
            break
        for it in batch:
            a = it.get("author") or it.get("commenter") or it.get("actor") or {}
            purl = (_first(a, "profile_url", "url", "profileUrl")
                    or _first(it, "profile_url", "commenter_url", "authorProfileUrl"))
            name = (_first(a, "name", "full_name") or _first(it, "author_name", "name") or "").strip()
            if not purl or not name:
                continue
            key = str(purl).split("?")[0].rstrip("/").lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "name": name,
                "profile_url": str(purl).split("?")[0].rstrip("/"),
                "comment_text": (_first(it, "text", "comment", "commentText") or "").strip(),
                "headline": _first(a, "headline", "occupation") or _first(it, "headline") or "",
            })
        if len(batch) < _PAGE:
            break
    _log.log("apify_commenters", metadata={"post": post_url[:80], "unique": len(out)})
    return out

