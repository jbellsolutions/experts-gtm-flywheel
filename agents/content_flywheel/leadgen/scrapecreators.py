"""ScrapeCreators LinkedIn client — the primary lead-gen collector.

you already owns ScrapeCreators credits and cost is **per request (1 credit),
not per comment**, which makes it the cheapest commenter collector available:

  * GET /v1/linkedin/profile?url=...  -> person headline + recent posts   (1 credit)
  * GET /v1/linkedin/post?url=...     -> {commentCount, comments:[...], ...} (1 credit)

The /post `comments` array gives each commenter's name + profile URL only (no
headline) — headline is fetched lazily via `profile()` for ICP-survivors only,
which is the real cost driver and why the pipeline pre-filters first.

Field shapes vary, so every extractor is defensive (tries several key names).
"""
from __future__ import annotations

import os
import re
from typing import Any

import httpx

from shared.logging.logger import AgentLogger

_log = AgentLogger("leadgen.scrapecreators")

BASE = os.getenv("SCRAPECREATORS_BASE", "https://api.scrapecreators.com").rstrip("/")
_TIMEOUT = 45


class ScrapeCreatorsError(RuntimeError):
    pass


def configured() -> bool:
    return bool(os.getenv("SCRAPECREATORS_API_KEY"))


def _key() -> str:
    k = os.getenv("SCRAPECREATORS_API_KEY")
    if not k:
        raise ScrapeCreatorsError("SCRAPECREATORS_API_KEY not set")
    return k


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """One credit-billed GET. Raises ScrapeCreatorsError on non-2xx."""
    with httpx.Client(timeout=_TIMEOUT) as c:
        r = c.get(f"{BASE}{path}", params=params, headers={"x-api-key": _key()})
    if r.status_code >= 300:
        raise ScrapeCreatorsError(f"GET {path} -> {r.status_code}: {r.text[:200]}")
    return r.json() or {}


# ── defensive field helpers ──────────────────────────────────────────────────

def _first(d: dict, *keys: str) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _to_int(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    # e.g. "2 - 1 Comment", "12 comments", "1,234"
    m = re.search(r"(\d[\d,]*)", str(v))
    return int(m.group(1).replace(",", "")) if m else None


# ── public API ────────────────────────────────────────────────────────────────

def profile(url_or_handle: str) -> dict[str, Any]:
    """GET /v1/linkedin/profile. Returns the raw JSON (headline + recent posts).

    Accepts a full URL or a vanity handle; normalises to a /in/ URL.
    """
    url = url_or_handle
    if not url.startswith("http"):
        url = f"https://www.linkedin.com/in/{url.strip('/@')}"
    return _get("/v1/linkedin/profile", {"url": url})


def recent_posts(profile_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull a normalised [{url, comment_count?}] list out of a profile payload.

    comment_count is best-effort — present it pre-filters before we spend /post
    credits; absent we just call post() and read commentCount there.
    """
    raw = (
        _first(profile_json, "posts", "recentPosts", "activity", "articles")
        or (profile_json.get("data") or {}).get("posts")
        or []
    )
    out: list[dict[str, Any]] = []
    for p in raw if isinstance(raw, list) else []:
        if not isinstance(p, dict):
            continue
        u = _first(p, "url", "link", "postUrl", "shareUrl")
        if not u:
            continue
        out.append({
            "url": u,
            "comment_count": _to_int(_first(
                p, "commentCount", "comments", "numComments", "interaction", "socialActivity")),
            "posted_at": _first(p, "datePublished", "postedAt", "created_at", "date"),
            "body": _first(p, "text", "description", "title") or "",
        })
    return out


def headline(profile_json: dict[str, Any]) -> str | None:
    return _first(profile_json, "headline", "occupation", "subtitle")


def about(profile_json: dict[str, Any]) -> str | None:
    return _first(profile_json, "about", "summary", "description")


def post(post_url: str) -> dict[str, Any]:
    """GET /v1/linkedin/post. Returns raw JSON incl. commentCount + comments[]."""
    return _get("/v1/linkedin/post", {"url": post_url})


def author(post_json: dict[str, Any]) -> dict[str, Any]:
    """The post author → {name, profile_url, followers}. For 'paste a post' mode,
    this person becomes an `influencers` row."""
    a = post_json.get("author")
    if isinstance(a, dict):
        url = _first(a, "url", "profileUrl", "linkedinUrl")
        return {
            "name": (_first(a, "name", "fullName") or "").strip() or None,
            "profile_url": url.split("?")[0].rstrip("/") if url else None,
            "followers": _to_int(_first(a, "followers", "followerCount")),
        }
    # some payloads put author fields at the top level
    url = _first(post_json, "authorUrl", "profileUrl")
    return {"name": _first(post_json, "name", "authorName"),
            "profile_url": url.split("?")[0].rstrip("/") if url else None,
            "followers": None}


def post_meta(post_json: dict[str, Any]) -> dict[str, Any]:
    """Post fields for storage → {comment_count, body, posted_at}."""
    return {
        "comment_count": comment_count(post_json),
        "body": (_first(post_json, "description", "text", "name", "title") or "").strip(),
        "posted_at": _first(post_json, "datePublished", "postedAt", "date", "created_at"),
    }


def comment_count(post_json: dict[str, Any]) -> int:
    return _to_int(_first(post_json, "commentCount", "comments_count", "numComments")) or 0


def commenters(post_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalise the /post comments array to [{name, profile_url, comment_text}].

    Only commenters with a resolvable profile URL are kept (URL is the dedup key).
    """
    raw = post_json.get("comments") or (post_json.get("data") or {}).get("comments") or []
    out: list[dict[str, Any]] = []
    for c in raw if isinstance(raw, list) else []:
        if not isinstance(c, dict):
            continue
        author = c.get("author")
        name = author.get("name") if isinstance(author, dict) else (author or _first(c, "name", "authorName"))
        url = (
            _first(c, "linkedinUrl", "profileUrl", "authorUrl", "url")
            or (author.get("url") if isinstance(author, dict) else None)
        )
        if not url:
            continue
        out.append({
            "name": (name or "").strip() or None,
            "profile_url": url.split("?")[0].rstrip("/"),
            "comment_text": (_first(c, "text", "comment", "body") or "").strip(),
        })
    return out
