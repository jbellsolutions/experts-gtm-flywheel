"""Parse URLs found inside content ideas.

YouTube → transcript via youtube-transcript-api.
Generic web → readable text via r.jina.ai (free, no auth).
"""
from __future__ import annotations

import re
from typing import Any

import requests

YT_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)"
    r"([A-Za-z0-9_-]{11})"
)
URL_RE = re.compile(r"https?://[^\s)>\]]+")


def extract_urls(text: str) -> list[str]:
    return URL_RE.findall(text or "")


def youtube_id(url: str) -> str | None:
    m = YT_RE.search(url)
    return m.group(1) if m else None


def parse_youtube(video_id: str) -> dict[str, Any]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        snippets = YouTubeTranscriptApi().fetch(video_id, languages=["en"])
        transcript = " ".join(s.text for s in snippets)
        return {
            "kind": "youtube",
            "url": f"https://youtu.be/{video_id}",
            "video_id": video_id,
            "transcript": transcript,
            "transcript_chars": len(transcript),
        }
    except Exception as e:
        return {"kind": "youtube", "video_id": video_id, "error": str(e)}


def parse_web(url: str) -> dict[str, Any]:
    try:
        r = requests.get(f"https://r.jina.ai/{url}", timeout=20)
        r.raise_for_status()
        body = r.text
        return {
            "kind": "web",
            "url": url,
            "body": body[:20000],
            "body_chars": len(body),
        }
    except Exception as e:
        return {"kind": "web", "url": url, "error": str(e)}


def parse(text: str) -> dict[str, Any]:
    """Parse the first useful URL in `text`. Returns {} if none."""
    for url in extract_urls(text):
        vid = youtube_id(url)
        if vid:
            return parse_youtube(vid)
        return parse_web(url)
    return {}
