"""Substack adapter — enqueues a browser job for the browser-runner service.

The browser-runner consumes from `flywheel:browser_jobs` and uses Browser Use
(LLM-driven Playwright wrapper) to publish via the persistent Substack profile.
"""
from __future__ import annotations

import os

from shared.redis_queue import enqueue, BROWSER_QUEUE


def _split_title(body: str) -> tuple[str, str]:
    lines = body.strip().split("\n", 1)
    if len(lines) == 2 and len(lines[0]) < 120:
        return lines[0].lstrip("# ").strip(), lines[1].strip()
    return body[:80], body


async def publish(draft: dict) -> dict:
    pub_url = (os.getenv("SUBSTACK_PUBLICATION_URL") or "").rstrip("/")
    if not pub_url:
        raise NotImplementedError(
            "Set SUBSTACK_PUBLICATION_URL (e.g. https://yourname.substack.com)"
        )
    title, body = _split_title(draft["body"])
    enqueue(BROWSER_QUEUE, {
        "platform": "substack",
        "draft_id": draft["id"],
        "publication_url": pub_url,
        "title": title,
        "body": body,
        "dry_run": bool((draft.get("metadata") or {}).get("dry_run")),
    })
    return {"url": None, "id": None, "queued": True}
