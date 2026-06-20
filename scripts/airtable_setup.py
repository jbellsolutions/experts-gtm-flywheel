#!/usr/bin/env python3
"""Create the lead-CRM Airtable schema for the organic flywheel.

The worker (agents/content_flywheel/leadgen/airtable.py) writes post commenters to
a **Contacts** table and reads its checkboxes; **Companies** is filled in Phase 2.
Field NAMES here MUST match the F_* constants in leadgen/airtable.py.

Usage (AIRTABLE_API_KEY env = the PAT):
  # create a brand-new base in a workspace, then add both tables:
  python scripts/airtable_setup.py --workspace wspXXXXXXXX --name "AI Guy Leads"
  # OR add the two tables to a base you already created (empty is fine):
  python scripts/airtable_setup.py --base appXXXXXXXX

Prints the base id to set as AIRTABLE_BASE_ID on the worker + dashboard.
Idempotent: skips tables that already exist.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.airtable.com/v0/meta"

_CHK = {"type": "checkbox", "options": {"icon": "check", "color": "greenBright"}}


def _select(*choices: str) -> dict:
    return {"type": "singleSelect", "options": {"choices": [{"name": c} for c in choices]}}


# Contacts — the leads. Primary field MUST be first (Name).
CONTACTS_FIELDS = [
    {"name": "Name", "type": "singleLineText"},
    {"name": "LinkedIn URL", "type": "singleLineText"},        # dedupe key (code-enforced)
    {"name": "Headline", "type": "singleLineText"},
    {"name": "What they said", "type": "multilineText"},
    {"name": "Source post", "type": "singleLineText"},
    {"name": "Company name", "type": "singleLineText"},
    {"name": "Email", "type": "email"},
    {"name": "Email status", **_select("none", "found", "drafted", "draft failed")},
    {"name": "Enrichment status", **_select("new", "enriched", "no contact")},
    {"name": "Draft subject", "type": "singleLineText"},
    {"name": "Draft email", "type": "multilineText"},
    {"name": "Voice", **_select("Your Voice")},
    {"name": "Offer", **_select("Your Offer")},
    {"name": "Enrich", **_CHK},
    {"name": "Create email", **_CHK},
    {"name": "Rerun", **_CHK},
    {"name": "Feedback", "type": "multilineText"},
    {"name": "Push to campaign", **_CHK},
]

COMPANIES_FIELDS = [
    {"name": "Name", "type": "singleLineText"},
    {"name": "Domain", "type": "singleLineText"},
    {"name": "Website", "type": "url"},
    {"name": "Industry", "type": "singleLineText"},
    {"name": "Size", "type": "singleLineText"},
    {"name": "Summary", "type": "multilineText"},
    {"name": "Enrich", **_CHK},
    {"name": "Status", "type": "singleLineText"},
]

TABLES = [
    {"name": "Contacts", "fields": CONTACTS_FIELDS},
    {"name": "Companies", "fields": COMPANIES_FIELDS},
]


def _req(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"Airtable {method} {url} -> {e.code}: {e.read().decode()[:400]}")


def create_base(token: str, workspace: str, name: str) -> str:
    out = _req("POST", f"{API}/bases", token, {"name": name, "workspaceId": workspace, "tables": TABLES})
    bid = out.get("id")
    print(f"Created base '{name}': {bid}")
    return bid


def ensure_tables(token: str, base: str) -> None:
    existing = {t["name"] for t in _req("GET", f"{API}/bases/{base}/tables", token).get("tables", [])}
    for t in TABLES:
        if t["name"] in existing:
            print(f"  table '{t['name']}' already exists — skip")
            continue
        _req("POST", f"{API}/bases/{base}/tables", token, t)
        print(f"  created table '{t['name']}'")


def ensure_link_field(token: str, base: str) -> None:
    """Add a 'Company' linked-record field to Contacts → Companies (Phase 2), idempotent."""
    tables = _req("GET", f"{API}/bases/{base}/tables", token).get("tables", [])
    by_name = {t["name"]: t for t in tables}
    contacts, companies = by_name.get("Contacts"), by_name.get("Companies")
    if not contacts or not companies:
        print("  (Contacts/Companies not found — create tables first)")
        return
    if any(f["name"] == "Company" for f in contacts.get("fields", [])):
        print("  Contacts.Company link already exists — skip")
        return
    _req("POST", f"{API}/bases/{base}/tables/{contacts['id']}/fields", token, {
        "name": "Company", "type": "multipleRecordLinks",
        "options": {"linkedTableId": companies["id"]}})
    print("  added Contacts.Company link → Companies")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", help="workspace id (wsp…) — creates a new base")
    ap.add_argument("--base", help="existing base id (app…) — adds the tables")
    ap.add_argument("--name", default="AI Guy Leads")
    a = ap.parse_args()
    token = os.getenv("AIRTABLE_API_KEY")
    if not token:
        sys.exit("Set AIRTABLE_API_KEY (the PAT).")
    if a.base:
        ensure_tables(token, a.base)
        base = a.base
    elif a.workspace:
        base = create_base(token, a.workspace, a.name)
    else:
        sys.exit("Pass --base appXXXX (existing base) or --workspace wspXXXX (new base).")
    ensure_link_field(token, base)
    print(f"\nDone. Set on the worker + dashboard:\n  AIRTABLE_BASE_ID={base}")


if __name__ == "__main__":
    main()
