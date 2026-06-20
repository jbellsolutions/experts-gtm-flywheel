"""When the queue runs low, generate brand-voice ideas as a fallback.

Threshold: < 5 pending ideas → generate 8.
"""
from __future__ import annotations

import asyncio
import json

from shared.logging.logger import AgentLogger

from ..repurposer import brand_voice
from ..repurposer.llm import complete
from . import store

_log = AgentLogger("idea_suggester")
THRESHOLD = 5
GENERATE_N = 8


def _prompt() -> tuple[str, str]:
    system = brand_voice.system_prompt("linkedin", "1") + (
        "\n\nYou're suggesting CONTENT IDEAS (not finished posts) for you to "
        "approve before they become content. Each idea: a single sentence — the "
        "angle/hook only. Mix Pillar 1 (ask-me-anything energy: clients, "
        "objections, AI tactics for SMBs) and Pillar 2 (certification journey, "
        "consultant building in public)."
    )
    user = (
        f"Suggest {GENERATE_N} fresh content ideas you would actually post "
        f"this week. Return JSON array of strings, no other text. Example: "
        f'["the dumbest objection I heard this week and the 1-line response that closes it", "..."]'
    )
    return system, user


async def maybe_suggest() -> None:
    pending = store.count_pending()
    if pending >= THRESHOLD:
        _log.log("queue_healthy", metadata={"pending": pending})
        return

    system, user = _prompt()
    try:
        raw = complete("idea_suggester", system, user)
    except Exception as e:
        _log.error("generation_failed", str(e))
        return

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        ideas = json.loads(raw.strip())
    except Exception as e:
        _log.error("parse_failed", str(e), metadata={"raw": raw[:300]})
        return

    inserted = 0
    for idea in ideas:
        if not isinstance(idea, str) or not idea.strip():
            continue
        store.insert_idea(source="auto_brand", content=idea.strip(), priority=30)
        inserted += 1
    _log.log("suggested", metadata={"pending_was": pending, "inserted": inserted})


if __name__ == "__main__":
    asyncio.run(maybe_suggest())
