"""Transcript ingest — pull YouTube auto-captions, fall back to Whisper."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from shared.auth.vault import get_secret
from shared.db import db
from shared.logging.logger import AgentLogger
from workflows.event_bus import bus

_log = AgentLogger("transcript-ingest")


def _detect_pillar(title: str) -> str:
    t = title.lower()
    p2_signals = ("journey", "behind the scenes", "lesson learned", "what we built",
                  "milestone", "the story", "how i started")
    if any(s in t for s in p2_signals):
        return "2"
    return "1"


def _latest_video() -> dict | None:
    """Return the most recent video on your channel via YouTube Data API."""
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", developerKey=get_secret("YOUTUBE_API_KEY"))
    channel_id = get_secret("YOUTUBE_CHANNEL_ID")
    res = yt.search().list(
        part="snippet", channelId=channel_id, order="date",
        type="video", maxResults=1,
    ).execute()
    items = res.get("items") or []
    if not items:
        return None
    item = items[0]
    return {
        "video_id": item["id"]["videoId"],
        "title": item["snippet"]["title"],
        "published_at": item["snippet"]["publishedAt"],
    }


def _fetch_transcript(video_id: str) -> str | None:
    """YouTube auto-captions first; OpenAI Whisper fallback if available."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        # New API (>=0.6.x): instance method that returns a FetchedTranscript
        # whose snippets each have .text. We try the convenience .fetch() first
        # and fall back to the explicit list/find_transcript path for non-en.
        try:
            fetched = api.fetch(video_id, languages=["en"])
            return " ".join(snippet.text for snippet in fetched)
        except Exception:
            transcript_list = api.list(video_id)
            transcript = transcript_list.find_transcript(["en", "en-US"])
            fetched = transcript.fetch()
            return " ".join(snippet.text for snippet in fetched)
    except Exception as e:
        _log.error("captions_unavailable", str(e), metadata={"video_id": video_id})

    if not os.getenv("OPENAI_API_KEY"):
        _log.log("whisper_skipped_no_key", metadata={"video_id": video_id})
        return None

    # Whisper fallback — yt-dlp audio + OpenAI Whisper API
    try:
        import subprocess, tempfile, openai
        with tempfile.TemporaryDirectory() as tmp:
            audio = f"{tmp}/{video_id}.m4a"
            subprocess.run(
                ["yt-dlp", "-f", "bestaudio[ext=m4a]", "-o", audio,
                 f"https://youtube.com/watch?v={video_id}"],
                check=True, capture_output=True,
            )
            with open(audio, "rb") as f:
                client = openai.OpenAI()
                tr = client.audio.transcriptions.create(model="whisper-1", file=f)
            return tr.text
    except Exception as e:
        _log.error("whisper_failed", str(e), metadata={"video_id": video_id})
        return None


async def ingest_latest() -> None:
    _log.log("ingest_start")
    video = _latest_video()
    if not video:
        _log.log("no_videos_found")
        return

    existing = db().table("transcripts").select("id").eq(
        "youtube_video_id", video["video_id"]
    ).execute()
    if existing.data:
        _log.log("already_ingested", metadata={"video_id": video["video_id"]})
        return

    text = _fetch_transcript(video["video_id"])
    if not text:
        _log.error("no_transcript", "captions and whisper both failed",
                   metadata={"video_id": video["video_id"]})
        return

    pillar = _detect_pillar(video["title"])
    inserted = db().table("transcripts").insert({
        "youtube_video_id": video["video_id"],
        "title": video["title"],
        "pillar": pillar,
        "raw_text": text,
        "cleaned_text": text,  # Phase 2: drop fillers
        "recorded_at": video["published_at"],
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    transcript_id = inserted.data[0]["id"] if inserted.data else None
    _log.log("ingested", metadata={
        "video_id": video["video_id"], "transcript_id": transcript_id,
        "pillar": pillar, "char_count": len(text),
    })
    if transcript_id:
        await bus.emit("transcript.ingested",
                       {"transcript_id": transcript_id, "pillar": pillar},
                       "transcript-ingest")


async def run() -> None:
    return
