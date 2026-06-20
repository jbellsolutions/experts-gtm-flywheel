"""FullEnrich bulk enrichment — name + company + LinkedIn URL → verified work email.

The decided contact source (see memory: leadgen-enrichment-stack). Waterfall across 20+
vendors, pay-per-hit, account-free. EMAILS ONLY — phones cost ~10x and are skipped here.
Key from FULLENRICH_API_KEY (Railway env). Ported from the validated super-browser script.
"""
from __future__ import annotations

import json
import os
import time

import httpx

from shared.logging.logger import AgentLogger

_log = AgentLogger("leadgen.fullenrich")

BASE = "https://app.fullenrich.com/api/v2"
ENRICH_FIELDS = ["contact.work_emails", "contact.personal_emails"]  # emails only (no phones)
_TIMEOUT = 90


def configured() -> bool:
    return bool(os.getenv("FULLENRICH_API_KEY"))


def _key() -> str | None:
    return os.getenv("FULLENRICH_API_KEY")


def _split_name(full: str) -> tuple[str, str]:
    parts = (full or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def _deep_find(obj, key_substrings, want_at=False) -> list[str]:
    found: list[str] = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, (dict, list)):
                    walk(v)
                elif isinstance(v, str) and any(s in k.lower() for s in key_substrings):
                    if (not want_at) or "@" in v:
                        found.append(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return found


def _extract(row: dict) -> tuple[str, str]:
    emails = _deep_find(row, ["email"], want_at=True)
    statuses = _deep_find(row, ["status", "verification", "deliverab"])
    email = next((e for e in emails if "@" in e), "")
    return email, (statuses[0] if statuses else "")


def enrich_bulk(leads: list[dict], *, poll_seconds: int = 600) -> dict:
    """leads: [{full_name, company?, domain?, linkedin_url?, lead_id}].
    Returns {lead_id: {email, email_status}} or {"__error__": ...}. Emails only."""
    key = _key()
    if not key:
        return {"__error__": "FULLENRICH_API_KEY not set"}
    data = []
    for i, lead in enumerate(leads):
        first, last = _split_name(lead.get("full_name", ""))
        c = {"first_name": first, "last_name": last, "enrich_fields": ENRICH_FIELDS,
             "custom": {"lead_id": str(lead.get("lead_id", i))}}
        if lead.get("company"):
            c["company_name"] = lead["company"]
        if lead.get("domain"):
            c["domain"] = lead["domain"]
        if lead.get("linkedin_url"):
            c["linkedin_url"] = lead["linkedin_url"]
        data.append(c)

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=_TIMEOUT) as cli:
            r = cli.post(f"{BASE}/contact/enrich/bulk", headers=headers,
                         json={"name": "flywheel batch", "data": data})
            if r.status_code not in (200, 201, 202):
                return {"__error__": f"trigger HTTP {r.status_code}: {r.text[:300]}"}
            trig = r.json()
            eid = trig.get("enrichment_id") or trig.get("id") or (trig.get("data") or {}).get("enrichment_id")
            if not eid:
                return {"__error__": f"no enrichment_id: {json.dumps(trig)[:300]}"}

            deadline = time.time() + poll_seconds
            results = None
            while time.time() < deadline:
                g = cli.get(f"{BASE}/contact/enrich/bulk/{eid}", headers=headers)
                j = g.json() if g.status_code < 300 else {}
                st = str(j.get("status") or "").upper()
                if st in ("FINISHED", "COMPLETED", "DONE", "SUCCESS", "ENRICHED"):
                    results = j
                    break
                if st in ("CREDITS_INSUFFICIENT", "FAILED", "ERROR", "CANCELLED", "CANCELED"):
                    need = (j.get("cost") or {}).get("credits")
                    return {"__error__": f"FullEnrich {st}" + (f" (~{need} credits needed)" if need else "")}
                time.sleep(10)
            if results is None:
                return {"__error__": f"timed out polling enrichment {eid}"}
    except Exception as e:  # noqa: BLE001
        return {"__error__": f"{type(e).__name__}: {e}"}

    rows = results.get("datas") or results.get("data") or results.get("results") or results.get("contacts") or []
    out: dict = {}
    for idx, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            continue
        lid = str((row.get("custom") or {}).get("lead_id", row.get("lead_id", idx)))
        email, estatus = _extract(row)
        out[lid] = {"email": email, "email_status": estatus}
    _log.log("fullenrich_done", metadata={"enrichment_id": eid, "leads": len(leads),
                                          "with_email": sum(1 for v in out.values() if v["email"])})
    return out
