"""Pull AI/automation trending topics from Hacker News + Reddit.

Free APIs, no auth. Run daily.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import requests

from shared.logging.logger import AgentLogger

from . import store

_log = AgentLogger("idea_trends_scraper")

KEYWORDS = re.compile(
    r"\b(ai|llm|gpt|claude|anthropic|openai|agent|agentic|automation|"
    r"workflow|n8n|make\.com|zapier|saas|startup|founder|prompt|model|"
    r"rag|copilot|cursor|coding agent|mcp)\b",
    re.I,
)
SUBREDDITS = ["MachineLearning", "automation", "smallbusiness", "Entrepreneur", "ChatGPTCoding"]


def _hn_top(limit: int = 30) -> list[dict[str, Any]]:
    try:
        ids = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
        ).json()[:limit]
    except Exception as e:
        _log.error("hn_top_failed", str(e))
        return []
    out = []
    for hid in ids:
        try:
            item = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{hid}.json", timeout=5
            ).json() or {}
        except Exception:
            continue
        title = item.get("title", "")
        if not KEYWORDS.search(title):
            continue
        out.append({
            "title": title,
            "url": item.get("url") or f"https://news.ycombinator.com/item?id={hid}",
            "score": item.get("score", 0),
            "source_id": f"hn:{hid}",
        })
    return out


def _reddit_top(sub: str, limit: int = 15) -> list[dict[str, Any]]:
    try:
        data = requests.get(
            f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}",
            headers={"User-Agent": "ai-guy-flywheel/1.0"},
            timeout=10,
        ).json()
    except Exception as e:
        _log.error("reddit_failed", str(e), metadata={"sub": sub})
        return []
    out = []
    for child in (data.get("data") or {}).get("children", []):
        d = child.get("data") or {}
        title = d.get("title", "")
        if not KEYWORDS.search(title):
            continue
        out.append({
            "title": title,
            "url": "https://reddit.com" + (d.get("permalink") or ""),
            "score": d.get("score", 0),
            "source_id": f"reddit:{d.get('id')}",
        })
    return out


def _already_seen(source_id: str) -> bool:
    res = (
        # SDK doesn't support jsonb path filter cleanly; query metadata->>source_id
        __import__("shared.db", fromlist=["db"]).db()
        .table("content_ideas").select("id").eq("source", "auto_trend")
        .filter("metadata->>source_id", "eq", source_id).limit(1).execute()
    )
    return bool(res.data)


async def scrape() -> None:
    items: list[dict[str, Any]] = []
    items.extend(_hn_top())
    for sub in SUBREDDITS:
        items.extend(_reddit_top(sub))

    items.sort(key=lambda x: x["score"], reverse=True)
    inserted = 0
    for it in items[:25]:
        if _already_seen(it["source_id"]):
            continue
        store.insert_idea(
            source="auto_trend",
            content=f"{it['title']} — {it['url']}",
            priority=50,
            metadata={"source_id": it["source_id"], "score": it["score"], "url": it["url"]},
        )
        inserted += 1
    _log.log("scrape_done", metadata={"considered": len(items), "inserted": inserted})


if __name__ == "__main__":
    asyncio.run(scrape())
