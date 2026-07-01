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


_settings_cache: dict[str, str] = {}


def _app_setting(key: str) -> str:
    """Read a dashboard-entered value from app_settings (cached once non-empty) so the
    operator can 'add your API key' in the Cold Email tab instead of only via env."""
    if _settings_cache.get(key):
        return _settings_cache[key]
    try:
        from . import store
        val = (store.get_setting(key) or "").strip()
    except Exception:  # noqa: BLE001
        val = ""
    if val:
        _settings_cache[key] = val
    return val


def _key() -> str:
    return (os.getenv("SMARTLEAD_API_KEY") or _app_setting("smartlead:api_key")).strip()


def configured() -> bool:
    return bool(_key())


def default_campaign() -> str:
    return (os.getenv("SMARTLEAD_CAMPAIGN_ID") or _app_setting("smartlead:campaign_id")).strip()


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


# ── Campaign creation (UNSTARTED) ────────────────────────────────────────────
# Brand-free defaults so this stays template-safe (synced to the public template).
# Email 1 rides the {{email_subject}}/{{email_body}} merge tags the drafter fills;
# the follow-ups are conversation-first — short, NO links, threaded subject, first
# name only (the cold-email playbook rules). Callers (the Hermes agent) may pass a
# richer sequence tailored to the offer.
DEFAULT_SETTINGS = {"send_as_plain_text": True, "enable_ai_esp_matching": True,
                    "follow_up_percentage": 100, "stop_lead_settings": "REPLY_TO_AN_EMAIL",
                    "track_settings": ["DONT_TRACK_EMAIL_OPEN", "DONT_TRACK_LINK_CLICK"]}
DEFAULT_SCHEDULE = {"timezone": "America/New_York", "days_of_the_week": [1, 2, 3, 4, 5],
                    "start_hour": "08:00", "end_hour": "17:00", "min_time_btw_emails": 8,
                    "max_new_leads_per_day": 50}
DEFAULT_SEQUENCE = {"sequences": [
    {"seq_number": 1, "seq_delay_details": {"delay_in_days": 1},
     "seq_variants": [{"subject": "{{email_subject}}", "email_body": "{{email_body}}",
                       "variant_label": "A"}]},
    {"seq_number": 2, "seq_delay_details": {"delay_in_days": 4},
     "seq_variants": [{"subject": "re: {{email_subject}}",
                       "email_body": "{{first_name}} — circling back on my note above. "
                                     "Worth a quick reply?", "variant_label": "A"}]},
    {"seq_number": 3, "seq_delay_details": {"delay_in_days": 4},
     "seq_variants": [{"subject": "re: {{email_subject}}",
                       "email_body": "{{first_name}}, I'll leave it here — if the timing's "
                                     "off, no worries. If it's worth a short conversation, "
                                     "just reply.", "variant_label": "A"}]},
]}


def _post_json(path: str, body: dict) -> dict:
    """POST to the SmartLead API (api_key param + browser UA). Raises on HTTP >= 300."""
    with httpx.Client(timeout=_TIMEOUT) as c:
        r = c.post(f"{_BASE}{path}", params={"api_key": _key()}, json=body, headers=_HEADERS)
    if r.status_code >= 300:
        raise RuntimeError(f"HTTP {r.status_code} on {path}: {r.text[:200]}")
    return r.json() if r.text else {}


def create_campaign(name: str, *, sequence: dict | None = None,
                    settings: dict | None = None, schedule: dict | None = None) -> dict:
    """Create a SmartLead campaign UNSTARTED: create → save sequence → settings →
    schedule. NEVER calls /start — the operator adds inboxes + starts it in SmartLead
    (that manual START is the review gate; nothing sends until then). Returns
    {"ok": True, "campaign_id": "..."} or {"error": ...}."""
    if not configured():
        return {"error": "SMARTLEAD_API_KEY not set"}
    if not name:
        return {"error": "campaign name required"}
    try:
        created = _post_json("/campaigns/create", {"name": name})
        cid = created.get("id") or created.get("campaign_id")
        if not cid:
            return {"error": f"no campaign id in response: {str(created)[:200]}"}
        _post_json(f"/campaigns/{cid}/sequences", sequence or DEFAULT_SEQUENCE)
        _post_json(f"/campaigns/{cid}/settings", settings or DEFAULT_SETTINGS)
        _post_json(f"/campaigns/{cid}/schedule", schedule or DEFAULT_SCHEDULE)
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
    _log.log("smartlead_create_campaign", metadata={"campaign": str(cid), "name": name})
    return {"ok": True, "campaign_id": str(cid)}
