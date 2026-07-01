"""Hermes — the cold-email campaign-builder chat agent.

Runs on the prospect-api service (the same Claude stack as the VA prospecting tool).
It holds a multi-turn conversation with the operator to gather ONE SmartLead cold-email
campaign spec, then signals `ready` with the spec. The DASHBOARD (which owns the Supabase
client) enqueues the leadgen_jobs row; the worker's `_run_hermes_campaign` creates the
UNSTARTED SmartLead campaign + ingests the leads to Airtable for review. Pure LLM here —
no DB writes, no sends. Its cold-email judgment comes from the shared cold_email_playbook
(distilled from the Single Brain SmartLead system).
"""
from __future__ import annotations

import json

from shared.logging.logger import AgentLogger

from ..leadgen import cold_email_playbook as playbook
from ..repurposer.llm import complete

_log = AgentLogger("hermes")

_MARK = "<<<CAMPAIGN"   # control block the model emits ONLY when the spec is confirmed


def _system(context: dict) -> str:
    offers = context.get("offers") or []          # [{slug,label}]
    voices_ = context.get("voices") or []         # [{id,label}]
    business = (context.get("business_info") or "").strip()
    has_upload = bool(context.get("uploaded_leads"))
    offer_lines = "\n".join(f'  - "{o.get("label")}"' for o in offers) or "  (none configured)"
    voice_lines = "\n".join(f'  - "{v.get("label")}"' for v in voices_) or "  (none configured)"
    upload_note = ("The operator HAS uploaded a lead list this session — 'list' is available."
                   if has_upload else
                   "No list uploaded yet — if they want a list source, tell them to use the "
                   "Upload button above the chat.")
    business_note = business or ("(none provided — you can ask the operator to add business "
                                 "info in the panel above so the copy is specific.)")
    return f"""You are Hermes, a cold-email campaign builder for this business. You talk with
the operator to design ONE SmartLead cold-email campaign, then hand it off to be built.
Be brief, concrete, and friendly — ask one or two questions at a time and suggest sensible
defaults so it moves fast.

{playbook.VOICE_RULES}

CAMPAIGN ANGLES you can suggest (pick/adapt one to the target + offer):
{playbook.frameworks_brief()}

WHAT YOU NEED before a campaign is ready:
  1. campaign_name — a short internal name.
  2. lead source — EITHER a LinkedIn post URL (we scrape its commenters) OR an uploaded
     list. {upload_note}
  3. offer_label — which offer this campaign sells. Options:
{offer_lines}
  4. voice_label — the voice. Options:
{voice_lines}
  5. framework — the angle key (from the list above) that best fits.

BUSINESS CONTEXT (use it to make the campaign specific):
{business_note}

HOW TO FINISH: keep chatting until you have all five AND the operator confirms "go". THEN,
and only then, end your message with a control block on its own line, exactly:
{_MARK} {{"campaign_name":"...","source_type":"post"|"list","post_url":"...(only if post)","offer_label":"...","voice_label":"...","framework":"<key>"}} >>>
Rules: valid single-line JSON; emit it ONLY after the operator confirms; if source_type is
"list", omit post_url (the uploaded leads attach automatically); use the EXACT offer/voice
labels from the options above. Before confirmation, NEVER emit the control block — just
converse. Always remind the operator that nothing sends until they add inboxes and hit START
in SmartLead — the leads land in Airtable to review first."""


def _transcript(messages: list[dict]) -> str:
    out = []
    for m in messages:
        role = "Operator" if m.get("role") == "user" else "Hermes"
        out.append(f"{role}: {m.get('content', '')}")
    out.append("Hermes:")
    return "\n".join(out)


def _extract_campaign(text: str) -> tuple[str, dict | None]:
    """Split a control block off the reply. Returns (clean_reply, campaign|None)."""
    i = text.find(_MARK)
    if i == -1:
        return text.strip(), None
    reply = text[:i].strip()
    tail = text[i + len(_MARK):]
    end = tail.find(">>>")
    blob = (tail[:end] if end != -1 else tail).strip()
    try:
        camp = json.loads(blob)
        if not isinstance(camp, dict):
            camp = None
    except Exception:  # noqa: BLE001
        camp = None
    return (reply or "Got it — building that campaign now."), camp


def chat(messages: list[dict], context: dict | None = None) -> dict:
    """One turn. messages = [{role:'user'|'assistant', content}]. Returns
    {reply, ready, campaign} — campaign is the spec dict once the operator confirms."""
    context = context or {}
    try:
        raw = complete("hermes_chat", _system(context), _transcript(messages))
    except Exception as e:  # noqa: BLE001
        _log.error("hermes_chat_failed", str(e))
        return {"reply": f"(Hermes hit an error: {e})", "ready": False, "campaign": None}
    reply, camp = _extract_campaign(raw)
    _log.log("hermes_turn", metadata={"ready": bool(camp), "turns": len(messages)})
    return {"reply": reply, "ready": bool(camp), "campaign": camp}
