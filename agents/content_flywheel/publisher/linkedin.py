"""LinkedIn adapter — Unipile API.

Posts go to your personal feed via POST /api/v1/posts (multipart/form-data
with `account_id` + `text`). Articles use the same endpoint with `is_article`
+ a `title` field. If Unipile rejects the `is_article` flag (their schema
varies by tenant version), we fall back to publishing as a long post.
"""
from __future__ import annotations

import os

import httpx

# LinkedIn (via Unipile /api/v1/posts) hard-caps content at 3000 characters —
# the `is_article` flag does NOT lift this. Anything longer 400s with
# errors/too_many_characters. We smart-truncate at a paragraph/sentence
# boundary under the limit so long-form editorial pieces still ship as a clean,
# self-contained long post instead of failing.
LINKEDIN_LIMIT = 3000


def _cap(text: str, limit: int = LINKEDIN_LIMIT) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Prefer the latest clean break (paragraph, then sentence) past 60% of the
    # limit so we don't chop mid-thought.
    for sep in ("\n\n", "\n", ". ", "! ", "? "):
        idx = cut.rfind(sep)
        if idx >= int(limit * 0.6):
            return cut[: idx + len(sep)].strip()
    idx = cut.rfind(" ")
    return (cut[:idx] if idx >= int(limit * 0.6) else cut).strip()


def _split_title(body: str) -> tuple[str, str]:
    """Pull the title (first non-empty line) from the body. Same heuristic
    used by publisher/substack.py:13 so editorial-stage drafts that put the
    title on line 1 work the same way across platforms."""
    lines = [ln for ln in body.strip().splitlines() if ln.strip()]
    if not lines:
        return "", body
    first = lines[0].lstrip("# ").strip()
    if len(first) < 120 and len(lines) > 1:
        rest = body.strip().split("\n", 1)[1].lstrip()
        return first, rest
    # No clear title — synthesize from first 80 chars of body.
    return body[:80].strip(), body


async def _download_media(urls: list[str], mime: str) -> list[tuple]:
    """Fetch rendered visual assets → [(filename, bytes, mime), ...].
    Skips any that fail; the caller treats a short list as 'fall back to text'."""
    ext = "mp4" if mime.startswith("video") else "png"
    out: list[tuple] = []
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        for i, u in enumerate(urls or []):
            try:
                resp = await client.get(u)
                resp.raise_for_status()
                name = (u.split("/")[-1].split("?")[0]) or f"media-{i+1:02d}.{ext}"
                out.append((name, resp.content, mime))
            except Exception:
                continue
    return out


def _publish_longform_via_browser(draft: dict) -> dict:
    """LinkedIn article + native newsletter publish via Browser Use (long-form;
    Unipile caps posts at 3000 chars and has no newsletter API). Enqueues a job
    for the browser-runner under the LinkedIn login profile. If that login isn't
    captured yet (BU_PROFILE_LINKEDIN unset), park the draft gracefully so it
    sits on the dashboard for manual publishing instead of error-looping."""
    from shared.redis_queue import enqueue, BROWSER_QUEUE
    fmt = (draft.get("format") or "article").lower()  # article | newsletter
    if not os.getenv("BU_PROFILE_LINKEDIN"):
        return {"skip": True,
                "reason": f"LinkedIn {fmt} needs the LinkedIn login captured",
                "hint": "Capture your LinkedIn login at cloud.browser-use.com and "
                        "set BU_PROFILE_LINKEDIN on the worker + browser-runner."}
    title, body = _split_title(draft["body"])
    visual = (draft.get("metadata") or {}).get("visual") or {}
    cover_url = visual.get("image_url") if visual.get("status") == "rendered" else None
    enqueue(BROWSER_QUEUE, {
        "platform": f"linkedin_{fmt}",   # linkedin_article | linkedin_newsletter
        "kind": fmt,
        "draft_id": draft["id"],
        "title": title,
        "body": body,
        "cover_url": cover_url,          # browser-runner sets it as the cover (best-effort)
        "dry_run": bool((draft.get("metadata") or {}).get("dry_run")),
    })
    return {"url": None, "id": None, "queued": True}


async def publish(draft: dict) -> dict:
    fmt = (draft.get("format") or "post").lower()
    if fmt in ("article", "newsletter"):
        return _publish_longform_via_browser(draft)

    api_key = os.getenv("UNIPILE_API_KEY")
    dsn = os.getenv("UNIPILE_DSN")
    account_id = os.getenv("UNIPILE_LINKEDIN_ACCOUNT_ID")
    if not (api_key and dsn and account_id):
        raise NotImplementedError(
            "Unipile not configured. Set UNIPILE_API_KEY, UNIPILE_DSN, "
            "UNIPILE_LINKEDIN_ACCOUNT_ID in .env."
        )

    headers = {"X-API-KEY": api_key}
    url = f"{dsn}/api/v1/posts"

    # Unipile's /api/v1/posts is a multer (multipart/form-data) endpoint.
    # `files=` with (None, value) tuples is the working shape (confirmed by
    # the 82+ live publishes). For articles, we add `title` and `is_article=true`.
    fmt = (draft.get("format") or "post").lower()
    if fmt == "article":
        title, body = _split_title(draft["body"])
        files = {
            "account_id": (None, account_id),
            "title":      (None, title),
            "text":       (None, _cap(body)),
            "is_article": (None, "true"),
        }
    else:
        files = {
            "account_id": (None, account_id),
            "text":       (None, _cap(draft["body"])),
        }

    # Attach the post's rendered visual as Unipile `attachments`. Multiple images
    # render as a swipeable LinkedIn gallery (our multi-image carousel). httpx
    # needs a LIST of tuples to repeat the `attachments` field. All-or-nothing for
    # carousels (never ship a partial deck); on any download miss we fall back to
    # the text-only dict above so a visual hiccup never blocks the post.
    visual = (draft.get("metadata") or {}).get("visual")
    if fmt != "article" and visual and visual.get("status") == "rendered":
        base_files = [
            ("account_id", (None, account_id)),
            ("text", (None, _cap(draft["body"]))),
        ]
        if visual.get("type") == "video" and visual.get("video_url"):
            # Single mp4 → native LinkedIn video post (same binary `attachments`
            # field as images). On a download miss, fall back to text-only.
            vid = await _download_media([visual["video_url"]], "video/mp4")
            if len(vid) == 1:
                files = base_files + [("attachments", vid[0])]
        else:
            img_urls = visual.get("slide_urls") or (
                [visual["image_url"]] if visual.get("image_url") else [])
            attach = await _download_media(img_urls, "image/png")
            if attach and len(attach) == len(img_urls):
                files = base_files + [("attachments", a) for a in attach]

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=headers, files=files)

        # Fallback: if Unipile rejects the article-specific fields (e.g. older
        # tenant version that doesn't recognize is_article), retry as a plain
        # long post so the content still ships and you can repost as
        # article manually. Surface the original error in metadata so we can
        # tighten the shape later.
        if r.status_code >= 300 and fmt == "article":
            original_err = f"{r.status_code}: {r.text[:300]}"
            fallback_files = {
                "account_id": (None, account_id),
                "text":       (None, _cap(draft["body"])),
            }
            r2 = await client.post(url, headers=headers, files=fallback_files)
            if r2.status_code >= 300:
                raise RuntimeError(
                    f"Unipile article {original_err} + post-fallback "
                    f"{r2.status_code}: {r2.text[:300]}"
                )
            r = r2
        elif r.status_code >= 300:
            raise RuntimeError(f"Unipile {r.status_code}: {r.text[:500]}")

        data = r.json()

    post_id = data.get("post_id") or data.get("id") or ""
    url_out = (
        data.get("share_url")
        or data.get("url")
        or (f"https://www.linkedin.com/feed/update/urn:li:activity:{post_id}/"
            if post_id else "")
    )
    return {"url": url_out, "id": post_id}
