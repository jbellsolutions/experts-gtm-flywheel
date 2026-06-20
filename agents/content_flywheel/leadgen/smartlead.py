"""SmartLead — push a drafted+emailed lead into a campaign (Phase 3).

Ports the ONE REST call the worker needs: add a lead to a campaign. your
smartlead-cli / smartlead-package owns everything else (campaign creation,
sequences, inboxes, scheduling, reply handling). The campaign's sequence must
reference the custom-field merge tags {{email_subject}} and {{email_body}} (the
package's sequence-json-template default) so each lead's drafted offer email
sends as-is. Config: SMARTLEAD_API_KEY (+ SMARTLEAD_CAMPAIGN_ID default).
"""
from __future__ import annotations

import os

import httpx

from shared.logging.logger import AgentLogger

_log = AgentLogger("leadgen.smartlead")

_BASE = "https://server.smartlead.ai/api/v1"
_TIMEOUT = 45
# server.smartlead.ai is Cloudflare-fronted and 1010-bans non-browser User-Agents
# (the default httpx UA gets blocked) — send a browser UA.
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "application/json"}


def configured() -> bool:
    return bool(os.getenv("SMARTLEAD_API_KEY"))


def default_campaign() -> str:
    return (os.getenv("SMARTLEAD_CAMPAIGN_ID") or "").strip()


def _key() -> str:
    return os.getenv("SMARTLEAD_API_KEY", "")


def _split_name(full: str) -> tuple[str, str]:
    parts = (full or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def add_lead(campaign_id: str, *, email: str, full_name: str | None = None,
             company: str | None = None, subject: str | None = None,
             body: str | None = None, linkedin_url: str | None = None) -> dict:
    """Add one lead to a SmartLead campaign with the drafted email carried in
    custom_fields (the campaign sequence merges {{email_subject}}/{{email_body}}).
    Returns {"ok": True, ...} or {"error": ...}."""
    if not configured():
        return {"error": "SMARTLEAD_API_KEY not set"}
    if not (campaign_id and email):
        return {"error": "campaign_id and email required"}
    first, last = _split_name(full_name or "")
    lead = {
        "email": email,
        "first_name": first,
        "last_name": last,
        "company_name": company or "",
        "custom_fields": {k: v for k, v in {"email_subject": subject, "email_body": body}.items() if v},
    }
    if linkedin_url:
        lead["linkedin_profile"] = linkedin_url
    # ignore_duplicate_leads_in_other_campaign=False keeps SmartLead's one-shot-per-email guard.
    payload = {"lead_list": [lead], "settings": {"ignore_duplicate_leads_in_other_campaign": False}}
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.post(f"{_BASE}/campaigns/{campaign_id}/leads",
                       params={"api_key": _key()}, json=payload, headers=_HEADERS)
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
    if r.status_code >= 300:
        return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
    data = r.json() if r.text else {}
    _log.log("smartlead_add", metadata={"campaign": campaign_id, "email": email,
                                        "uploaded": data.get("upload_count"),
                                        "dup": data.get("already_added_to_campaign")})
    return {"ok": True, "raw": data}
