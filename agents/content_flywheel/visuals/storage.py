"""Supabase Storage helpers for rendered post visuals.

Public bucket `post-media` (the images get posted publicly to LinkedIn anyway,
so public URLs keep the dashboard <img> + publisher download trivial).
"""
from __future__ import annotations

from shared.db import db
from shared.logging.logger import AgentLogger

_log = AgentLogger("visuals-storage")
BUCKET = "post-media"


# PNG cards/slides + mp4 motion clips share the bucket. 50MB covers short
# HiggsField clips (5-10s); LinkedIn/Unipile reject oversized media anyway.
_MIMES = ["image/png", "video/mp4"]
_SIZE_LIMIT = "52428800"  # 50 MB


def ensure_bucket() -> None:
    """Create (or widen) the public bucket so it accepts PNG + mp4 (idempotent)."""
    try:
        db().storage.create_bucket(
            BUCKET,
            options={"public": True, "allowed_mime_types": _MIMES,
                     "file_size_limit": _SIZE_LIMIT},
        )
        _log.log("bucket_created", metadata={"bucket": BUCKET})
    except Exception:
        # Already exists — widen it so video uploads aren't rejected by the
        # png-only/5MB limits the bucket was first created with.
        try:
            db().storage.update_bucket(
                BUCKET,
                options={"public": True, "allowed_mime_types": _MIMES,
                         "file_size_limit": _SIZE_LIMIT},
            )
        except Exception:
            pass


def upload_bytes(path: str, data: bytes, content_type: str) -> str:
    """Upload bytes (upsert) with an explicit content type; return public URL."""
    bucket = db().storage.from_(BUCKET)
    opts = {"content-type": content_type, "upsert": "true",
            "cache-control": "31536000"}
    try:
        bucket.upload(path, data, opts)
    except Exception:
        bucket.update(path, data, {"content-type": content_type})
    return db().storage.from_(BUCKET).get_public_url(path)


def upload_png(path: str, data: bytes) -> str:
    """Upload PNG bytes (upsert) and return the public URL."""
    return upload_bytes(path, data, "image/png")


def upload_mp4(path: str, data: bytes) -> str:
    """Upload mp4 bytes (upsert) and return the public URL."""
    return upload_bytes(path, data, "video/mp4")
