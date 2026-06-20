#!/usr/bin/env python3
"""Configure a SmartLead campaign for your flywheel.

The flywheel drafts a per-lead offer email (Airtable Contacts → Create email) and
pushes the lead with custom_fields.email_subject / email_body. This script sets up
the campaign that sends it: a 4-step sequence (email 1 = the per-lead draft via
{{email_subject}}/{{email_body}} merge tags; emails 2-4 = AI-Guy follow-ups with
SmartLead seq_variants for variation — no raw Spintax, which SmartLead can't render),
plain-text / no-tracking settings, and a weekday schedule.

Usage (SMARTLEAD_API_KEY in env):
  python scripts/smartlead_setup.py --campaign <your-campaign-id>
  python scripts/smartlead_setup.py --create --name "Cold Outreach"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://server.smartlead.ai/api/v1"

# ── Follow-ups (TEMPLATE — your offer, in your voice). Email 1 is the per-lead draft. ──
# Replace these with 2-4 follow-ups. The onboarding assistant drafts them from your
# offer + voice; keep them human, specific, no hype. Sign with your name.
E2A = (
    "{{first_name}} — following up on this.\n\n"
    "[TODO: restate the core value of your offer in plain words — the specific outcome "
    "you create and who it's for. No hype, no pressure.]\n\n"
    "Worth a quick look?\n\n[Your name]"
)
E2B = (
    "{{first_name}}, one more angle.\n\n"
    "[TODO: a different way into the same offer — a proof point, a contrast with the "
    "usual way, or the cost of not solving this.]\n\n"
    "Open to a conversation?\n\n[Your name]"
)
E3A = ("{{first_name}}, did this land? [TODO: a one-line nudge tied to their world.]\n\n[Your name]")
E3B = ("{{first_name}} — quick one: [TODO: a single sharp question about their priority.]\n\n[Your name]")
E4A = ("{{first_name}}, last note from me. [TODO: a gracious close — if it's not a priority "
       "right now, no hard feelings; if it is, it's worth a few minutes.]\n\n[Your name]")

SEQUENCES = {"sequences": [
    {"seq_number": 1, "seq_delay_details": {"delay_in_days": 1},
     "seq_variants": [{"subject": "{{email_subject}}", "email_body": "{{email_body}}", "variant_label": "A"}]},
    {"seq_number": 2, "seq_delay_details": {"delay_in_days": 4},
     "seq_variants": [{"subject": "re: {{email_subject}}", "email_body": E2A, "variant_label": "A"},
                      {"subject": "re: {{email_subject}}", "email_body": E2B, "variant_label": "B"}]},
    {"seq_number": 3, "seq_delay_details": {"delay_in_days": 3},
     "seq_variants": [{"subject": "re: {{email_subject}}", "email_body": E3A, "variant_label": "A"},
                      {"subject": "re: {{email_subject}}", "email_body": E3B, "variant_label": "B"}]},
    {"seq_number": 4, "seq_delay_details": {"delay_in_days": 4},
     "seq_variants": [{"subject": "last one", "email_body": E4A, "variant_label": "A"}]},
]}

SETTINGS = {"send_as_plain_text": True, "enable_ai_esp_matching": True,
            "follow_up_percentage": 100, "stop_lead_settings": "REPLY_TO_AN_EMAIL",
            "track_settings": ["DONT_TRACK_EMAIL_OPEN", "DONT_TRACK_LINK_CLICK"]}

SCHEDULE = {"timezone": "America/New_York", "days_of_the_week": [1, 2, 3, 4, 5],
            "start_hour": "08:00", "end_hour": "17:00", "min_time_btw_emails": 8,
            "max_new_leads_per_day": 50}


def _post(path: str, key: str, body: dict) -> dict:
    url = f"{BASE}{path}?api_key={key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          # Cloudflare 1010-bans the bare urllib UA.
                                          "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"POST {path} -> {e.code}: {e.read().decode()[:400]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign")
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--name", default="Cold Outreach")
    a = ap.parse_args()
    key = os.getenv("SMARTLEAD_API_KEY") or sys.exit("Set SMARTLEAD_API_KEY")

    cid = a.campaign
    if a.create or not cid:
        out = _post("/campaigns/create", key, {"name": a.name})
        cid = out.get("id")
        print(f"created campaign {cid} ({a.name})")
    _post(f"/campaigns/{cid}/sequences", key, SEQUENCES)
    print("  sequence saved (4 steps; email 1 = per-lead draft, 2-4 = follow-ups)")
    _post(f"/campaigns/{cid}/settings", key, SETTINGS)
    print("  settings: plain text, no open/click tracking, stop-on-reply, 100% follow-up")
    _post(f"/campaigns/{cid}/schedule", key, SCHEDULE)
    print("  schedule: Mon-Fri 08:00-17:00 ET, 8 min between, 50 new leads/day")
    print(f"\nDone. SMARTLEAD_CAMPAIGN_ID={cid}\nNext: add the BDR's inboxes in SmartLead, then START.")


if __name__ == "__main__":
    main()
