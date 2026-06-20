"""Poll your Slack DMs to the bot for new content ideas.

Read calls (conversations.list, conversations.history) prefer SLACK_USER_TOKEN
(xoxp) when set — it carries the broader im:history/channels:history scopes.
Write calls (chat.postMessage acks) always use SLACK_BOT_TOKEN so the
acknowledgement comes from the bot's identity.

Polls every 2 min via cron.
"""
from __future__ import annotations

import asyncio
from typing import Any

import requests

from shared.auth.vault import get_secret
from shared.logging.logger import AgentLogger

from . import store, url_parser

_log = AgentLogger("idea_slack_poller")
_KV = "slack_idea_poller_last_ts"
_OPERATOR_USER_ID = "U0XXXXXXXXX"


def _read_token() -> str:
    """Prefer user token (xoxp) for read calls — it has im:history."""
    import os
    return os.getenv("SLACK_USER_TOKEN") or get_secret("SLACK_BOT_TOKEN")


def _slack(method: str, **params) -> dict[str, Any]:
    token = _read_token()
    r = requests.get(
        f"https://slack.com/api/{method}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"slack {method} failed: {data}")
    return data


def _slack_post(method: str, **payload) -> dict[str, Any]:
    token = get_secret("SLACK_BOT_TOKEN")
    r = requests.post(
        f"https://slack.com/api/{method}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json=payload,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _find_dm_channel() -> str | None:
    """Find the IM (DM) channel between bot and you."""
    cursor = ""
    while True:
        params = {"types": "im", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        data = _slack("conversations.list", **params)
        for ch in data.get("channels", []):
            if ch.get("user") == _OPERATOR_USER_ID:
                return ch["id"]
        cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            return None


def _ack(channel: str, idea_id: str, parsed: dict[str, Any]) -> None:
    bits = [f":bulb: queued idea `{idea_id[:8]}` (priority 90)"]
    if parsed.get("kind") == "youtube":
        bits.append(f"• parsed YouTube transcript ({parsed.get('transcript_chars', 0)} chars)")
    elif parsed.get("kind") == "web":
        bits.append(f"• fetched page ({parsed.get('body_chars', 0)} chars)")
    if parsed.get("error"):
        bits.append(f"• :warning: parse error: {parsed['error']}")
    _slack_post("chat.postMessage", channel=channel, text="\n".join(bits))


async def poll() -> None:
    try:
        channel = _find_dm_channel()
    except Exception as e:
        _log.error("dm_lookup_failed", str(e))
        return
    if not channel:
        _log.log("no_dm_channel")
        return

    last_ts = store.kv_get(_KV, "0")
    try:
        history = _slack("conversations.history", channel=channel, oldest=last_ts, limit=50)
    except Exception as e:
        _log.error("history_failed", str(e))
        return

    msgs = sorted(history.get("messages", []), key=lambda m: float(m.get("ts", 0)))
    new_count = 0
    max_ts = last_ts
    for m in msgs:
        ts = m.get("ts", "0")
        if float(ts) <= float(last_ts):
            continue
        if m.get("user") != _OPERATOR_USER_ID:
            max_ts = ts
            continue
        text = (m.get("text") or "").strip()
        if not text:
            max_ts = ts
            continue

        parsed = url_parser.parse(text)
        idea = store.insert_idea(
            source="slack",
            content=text,
            priority=90,
            parsed_content=parsed,
            metadata={"slack_ts": ts, "channel": channel},
        )
        try:
            _ack(channel, idea["id"], parsed)
        except Exception as e:
            _log.error("ack_failed", str(e))
        new_count += 1
        max_ts = ts

    if max_ts != last_ts:
        store.kv_set(_KV, max_ts)
    _log.log("poll_done", metadata={"new": new_count, "last_ts": max_ts})


if __name__ == "__main__":
    asyncio.run(poll())
