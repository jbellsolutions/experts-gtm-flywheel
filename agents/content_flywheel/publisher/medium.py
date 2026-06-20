"""Medium adapter — enqueues browser job for browser-runner."""
from __future__ import annotations

from shared.redis_queue import enqueue, BROWSER_QUEUE


async def publish(draft: dict) -> dict:
    body = draft["body"]
    title, content = (body.split("\n", 1) if "\n" in body else (body[:80], body))
    enqueue(BROWSER_QUEUE, {
        "platform": "medium",
        "draft_id": draft["id"],
        "publication_url": "https://medium.com/new-story",
        "title": title.lstrip("# ").strip(),
        "body": content.strip(),
        "dry_run": bool((draft.get("metadata") or {}).get("dry_run")),
    })
    return {"url": None, "id": None, "queued": True}
