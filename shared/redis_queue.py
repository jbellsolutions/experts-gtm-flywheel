"""Tiny Redis queue helper for handing browser jobs from worker -> browser-runner.

Uses Redis lists (LPUSH/BRPOP) — simplest possible queue. No bells.
On Railway, REDIS_URL is set automatically when the Redis plugin is attached.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def _r():
    import redis
    return redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"),
                                decode_responses=True)


def enqueue(queue: str, payload: dict[str, Any]) -> None:
    _r().lpush(queue, json.dumps(payload))


def dequeue(queue: str, timeout: int = 30) -> dict[str, Any] | None:
    """Blocking pop with timeout. Returns None on timeout."""
    res = _r().brpop([queue], timeout=timeout)
    if not res:
        return None
    _, raw = res
    return json.loads(raw)


# Queue names — keep consistent across producer + consumer
BROWSER_QUEUE = "flywheel:browser_jobs"
