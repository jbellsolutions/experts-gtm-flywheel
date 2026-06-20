"""Shared Supabase client for the content flywheel.

Reuses the same env vars as shared/memory/supabase_backend.py.
"""
from __future__ import annotations

from functools import lru_cache

from shared.auth.vault import get_secret


@lru_cache(maxsize=1)
def db():
    """Cached Supabase client."""
    from supabase import create_client
    return create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_SERVICE_ROLE_KEY"))
