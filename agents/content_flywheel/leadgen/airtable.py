"""Airtable client — the lead CRM (Contacts + Companies), replacing the dashboard
leads table.

Post commenters land in the **Contacts** table (the BDR's working surface). A
poll-cron (pipeline.drain_airtable) reads the per-row checkboxes — Enrich /
Create email / Rerun — runs the action, writes results back, and clears the box.
Idempotent on the LinkedIn URL field. Config: AIRTABLE_API_KEY (PAT) + AIRTABLE_BASE_ID.
Field NAMES here must match the schema created by scripts/airtable_setup.py.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from shared.logging.logger import AgentLogger

_log = AgentLogger("leadgen.airtable")

_API = "https://api.airtable.com/v0"
_TIMEOUT = 30

CONTACTS = "Contacts"
COMPANIES = "Companies"

# ── Contacts fields (exact Airtable column names) ─────────────────────────────
F_NAME = "Name"
F_URL = "LinkedIn URL"          # unique = dedupe key
F_HEADLINE = "Headline"
F_SAID = "What they said"
F_POST = "Source post"
F_COMPANY = "Company name"
F_EMAIL = "Email"
F_EMAIL_STATUS = "Email status"
F_ENRICH_STATUS = "Enrichment status"
F_SUBJECT = "Draft subject"
F_BODY = "Draft email"
F_VOICE = "Voice"              # single-select: AI Guy / Human-Loop / AI Reality
F_OFFER = "Offer"             # single-select: Your Offer
F_ENRICH = "Enrich"          # checkbox
F_CREATE = "Create email"    # checkbox
F_RERUN = "Rerun"            # checkbox
F_FEEDBACK = "Feedback"      # long text (drives Rerun)
F_PUSH = "Push to campaign"  # checkbox (Phase 3)
F_CONTACT_COMPANY = "Company"  # linked-record field on Contacts → Companies (Phase 2)

# ── Companies fields ──────────────────────────────────────────────────────────
CO_NAME = "Name"
CO_DOMAIN = "Domain"
CO_WEBSITE = "Website"
CO_INDUSTRY = "Industry"
CO_SIZE = "Size"
CO_SUMMARY = "Summary"
CO_ENRICH = "Enrich"   # checkbox
CO_STATUS = "Status"

# Airtable single-select LABEL -> internal id/slug used by email_draft / store.
VOICE_LABEL_TO_ID = {"Your Voice": "ai_guy"}  # Airtable Voice label -> brand_voice slot
OFFER_LABEL_TO_SLUG = {"Your Offer": "your_offer"}  # Airtable Offer label -> framework slug


def configured() -> bool:
    return bool(os.getenv("AIRTABLE_API_KEY") and os.getenv("AIRTABLE_BASE_ID"))


def _base() -> str:
    return os.getenv("AIRTABLE_BASE_ID", "")


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.getenv('AIRTABLE_API_KEY', '')}",
            "Content-Type": "application/json"}


def _url(table: str) -> str:
    return f"{_API}/{_base()}/{table}"


def base_url() -> str:
    """Human URL to the base (for the dashboard 'open Airtable' link)."""
    b = _base()
    return f"https://airtable.com/{b}" if b else ""


def _find(table: str, field: str, value: str) -> str | None:
    """Record id where {field} == value, else None."""
    esc = str(value).replace("\\", "\\\\").replace('"', '\\"')
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.get(_url(table), headers=_headers(),
                      params={"filterByFormula": f'{{{field}}}="{esc}"', "maxRecords": 1})
    except Exception as e:  # noqa: BLE001
        _log.error("airtable_find_err", str(e))
        return None
    if r.status_code >= 300:
        _log.error("airtable_find", f"{r.status_code}: {r.text[:160]}")
        return None
    recs = (r.json() or {}).get("records") or []
    return recs[0]["id"] if recs else None


def create_if_new(fields: dict[str, Any]) -> str | None:
    """POST a Contacts row unless one with this LinkedIn URL already exists
    (dedupe). Returns the new record id, or None on dup / error."""
    url_val = fields.get(F_URL)
    if url_val and _find(CONTACTS, F_URL, url_val):
        return None
    clean = {k: v for k, v in fields.items() if v not in (None, "")}
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.post(_url(CONTACTS), headers=_headers(), json={"fields": clean, "typecast": True})
    except Exception as e:  # noqa: BLE001
        _log.error("airtable_create_err", str(e))
        return None
    if r.status_code >= 300:
        _log.error("airtable_create", f"{r.status_code}: {r.text[:200]}")
        return None
    return (r.json() or {}).get("id")


def flagged(checkbox_field: str, limit: int = 25) -> list[dict[str, Any]]:
    """Contacts rows where the given checkbox is checked → [{id, fields}, ...]."""
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.get(_url(CONTACTS), headers=_headers(),
                      params={"filterByFormula": f"{{{checkbox_field}}}=1", "pageSize": limit})
    except Exception as e:  # noqa: BLE001
        _log.error("airtable_flagged_err", str(e))
        return []
    if r.status_code >= 300:
        _log.error("airtable_flagged", f"{checkbox_field} {r.status_code}: {r.text[:160]}")
        return []
    return (r.json() or {}).get("records") or []


def patch_contact(record_id: str, fields: dict[str, Any]) -> bool:
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.patch(f"{_url(CONTACTS)}/{record_id}", headers=_headers(),
                        json={"fields": fields, "typecast": True})
    except Exception as e:  # noqa: BLE001
        _log.error("airtable_patch_err", str(e))
        return False
    if r.status_code >= 300:
        _log.error("airtable_patch", f"{r.status_code}: {r.text[:200]}")
        return False
    return True


# ── Companies (Phase 2) ───────────────────────────────────────────────────────

def _find_rec(table: str, field: str, value: str) -> dict | None:
    """Full record {id, fields} where {field}==value, else None."""
    esc = str(value).replace("\\", "\\\\").replace('"', '\\"')
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.get(_url(table), headers=_headers(),
                      params={"filterByFormula": f'{{{field}}}="{esc}"', "maxRecords": 1})
    except Exception as e:  # noqa: BLE001
        _log.error("airtable_findrec_err", str(e))
        return None
    if r.status_code >= 300:
        _log.error("airtable_findrec", f"{r.status_code}: {r.text[:160]}")
        return None
    recs = (r.json() or {}).get("records") or []
    return recs[0] if recs else None


def upsert_company(name: str) -> tuple[str | None, bool]:
    """Find/create a Companies row by Name. Returns (record_id, already_enriched)
    so the caller can skip re-enriching a company that already has a summary."""
    rec = _find_rec(COMPANIES, CO_NAME, name)
    if rec:
        return rec["id"], bool((rec.get("fields") or {}).get(CO_SUMMARY))
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.post(_url(COMPANIES), headers=_headers(),
                       json={"fields": {CO_NAME: name}, "typecast": True})
    except Exception as e:  # noqa: BLE001
        _log.error("airtable_company_create_err", str(e))
        return None, False
    if r.status_code >= 300:
        _log.error("airtable_company_create", f"{r.status_code}: {r.text[:200]}")
        return None, False
    return (r.json() or {}).get("id"), False


def patch_company(record_id: str, fields: dict[str, Any]) -> bool:
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.patch(f"{_url(COMPANIES)}/{record_id}", headers=_headers(),
                        json={"fields": fields, "typecast": True})
    except Exception as e:  # noqa: BLE001
        _log.error("airtable_company_patch_err", str(e))
        return False
    if r.status_code >= 300:
        _log.error("airtable_company_patch", f"{r.status_code}: {r.text[:200]}")
        return False
    return True


def link_contact_company(contact_id: str, company_id: str) -> bool:
    """Point the Contact's Company link field at the company record."""
    return patch_contact(contact_id, {F_CONTACT_COMPANY: [company_id]})


def flagged_companies(limit: int = 25) -> list[dict[str, Any]]:
    """Companies rows with the Enrich checkbox set (manual re-enrich)."""
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.get(_url(COMPANIES), headers=_headers(),
                      params={"filterByFormula": f"{{{CO_ENRICH}}}=1", "pageSize": limit})
    except Exception as e:  # noqa: BLE001
        _log.error("airtable_flagged_co_err", str(e))
        return []
    if r.status_code >= 300:
        _log.error("airtable_flagged_co", f"{r.status_code}: {r.text[:160]}")
        return []
    return (r.json() or {}).get("records") or []
