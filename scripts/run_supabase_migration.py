#!/usr/bin/env python3
"""Run the content_flywheel migration against Supabase.

Two execution paths, in order of preference:

  1. SUPABASE_ACCESS_TOKEN (a Personal Access Token from
     https://supabase.com/dashboard/account/tokens) — uses the Management API,
     which can execute arbitrary SQL.

  2. SUPABASE_DB_URL (the full Postgres connection string, found in the
     project's Database settings) — uses psycopg.

If neither is set, prints the SQL editor deep-link for manual paste.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import httpx

MIGRATION = Path(__file__).resolve().parent / "migrations" / "001_content_flywheel.sql"


def project_ref(url: str) -> str:
    m = re.match(r"https?://([^.]+)\.supabase\.co", url)
    if not m:
        raise SystemExit(f"Can't parse project ref from SUPABASE_URL: {url}")
    return m.group(1)


def via_management_api() -> bool:
    token = os.getenv("SUPABASE_ACCESS_TOKEN")
    url = os.getenv("SUPABASE_URL")
    if not (token and url):
        return False
    ref = project_ref(url)
    sql = MIGRATION.read_text()
    r = httpx.post(
        f"https://api.supabase.com/v1/projects/{ref}/database/query",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json={"query": sql},
        timeout=60,
    )
    if r.status_code >= 300:
        print(f"❌ Management API error {r.status_code}: {r.text}")
        return False
    print(f"✅ Migration applied via Management API. Response: {r.text[:200]}")
    return True


def via_psycopg() -> bool:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        return False
    try:
        import psycopg
    except ImportError:
        print("Install psycopg: pip install 'psycopg[binary]'")
        return False
    sql = MIGRATION.read_text()
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    print("✅ Migration applied via direct psycopg connection.")
    return True


def manual_link() -> None:
    url = os.getenv("SUPABASE_URL", "")
    if url:
        ref = project_ref(url)
        link = f"https://supabase.com/dashboard/project/{ref}/sql/new"
    else:
        link = "https://supabase.com/dashboard"
    print(
        "ℹ️  No SUPABASE_ACCESS_TOKEN or SUPABASE_DB_URL set.\n"
        f"   Open: {link}\n"
        f"   Paste: {MIGRATION}\n"
        "   Click Run.\n"
        "\nOR set SUPABASE_ACCESS_TOKEN and re-run this script for fully automated apply."
    )


if __name__ == "__main__":
    if via_management_api() or via_psycopg():
        sys.exit(0)
    manual_link()
    sys.exit(1)
