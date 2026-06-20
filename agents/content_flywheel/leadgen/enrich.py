"""Bright Data enrichment — email/phone for ICP-fit leads only.

you explicitly relaxed his no-paid-enrichment rule FOR THIS PIPELINE ONLY.
We feed commenter profile URLs to Bright Data's "LinkedIn people profiles -
contact fields enriched" dataset (gd_me5ppxjr2ge6icjuh0) via the v3 REST flow:

    trigger -> poll progress -> download snapshot

Honest expectation: email is achievable, phone hit-rate is genuinely low. The
exact output field names are dataset-defined, so extraction is defensive — the
FIRST real run should confirm which of {email, phone} actually populate.
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

from shared.logging.logger import AgentLogger

_log = AgentLogger("leadgen.enrich")

_BASE = "https://api.brightdata.com/datasets/v3"
# Bright Data LinkedIn people collector — the ONLY active, triggerable LinkedIn
# people dataset (docs-confirmed). Returns name/position/current_company/about
# (LinkedIn doesn't expose email/phone — those come from a separate contact source).
# Verified live: trigger by profile URL -> real profile record.
DATASET_ID = os.getenv("BRIGHTDATA_ENRICH_DATASET", "gd_l1viktl72bvl7bjuj0")
_TIMEOUT = 60
_POLL_EVERY = 8          # seconds
_POLL_MAX = 75           # attempts (~10 min ceiling)


class EnrichError(RuntimeError):
    pass


def configured() -> bool:
    return bool(_token_opt())


def _token_opt() -> str | None:
    return os.getenv("BRIGHT_DATA_API_TOKEN") or os.getenv("BRIGHTDATA_API_TOKEN")


def _token() -> str:
    t = _token_opt()
    if not t:
        raise EnrichError("BRIGHT_DATA_API_TOKEN not set")
    return t


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}


def _first(d: dict, *keys: str) -> Any:
    for k in keys:
        v = d.get(k) if isinstance(d, dict) else None
        if v not in (None, "", [], {}):
            return v
    return None


def _pick_contact(rec: dict[str, Any]) -> dict[str, str | None]:
    email = _first(rec, "email", "work_email", "personal_email")
    if isinstance(email, list):
        email = email[0] if email else None
    phone = _first(rec, "phone", "phone_number", "phone_numbers", "mobile")
    if isinstance(phone, list):
        phone = phone[0] if phone else None
    url = _first(rec, "url", "input_url", "linkedin_url", "profile_url")
    # The dataset is a PROFILES dataset, so it also carries profile context the
    # email-draft step uses (name / headline / about).
    return {"profile_url": (str(url).split("?")[0].rstrip("/") if url else None),
            "email": email, "phone": phone,
            "name": _first(rec, "name", "full_name", "fullName"),
            "headline": _first(rec, "headline", "position", "occupation", "sub_title"),
            "about": _first(rec, "about", "summary", "bio"),
            "company": _company(rec)}


def _company(rec: dict) -> str | None:
    cc = rec.get("current_company")
    if isinstance(cc, dict) and cc.get("name"):
        return cc["name"]
    return _first(rec, "current_company_name", "company", "company_name")


_CHUNK = 10  # BD profile snapshots time out on big batches — keep them small


def enrich(profile_urls: list[str]) -> dict[str, dict[str, str | None]]:
    """{profile_url: {name, headline, about, company, email, phone}} — BD profile data
    (company/title), chunked ≤10 so a big batch doesn't blow the poll window."""
    out: dict[str, dict[str, str | None]] = {}
    for i in range(0, len(profile_urls), _CHUNK):
        chunk = profile_urls[i:i + _CHUNK]
        try:
            out.update(_enrich_chunk(chunk))
        except Exception as e:  # noqa: BLE001
            _log.error("enrich_chunk_failed", str(e), metadata={"n": len(chunk)})
    return out


def _enrich_chunk(profile_urls: list[str]) -> dict[str, dict[str, str | None]]:
    """One BD snapshot for a small batch of profile URLs."""
    if not profile_urls:
        return {}

    # 1. trigger
    with httpx.Client(timeout=_TIMEOUT) as c:
        r = c.post(f"{_BASE}/trigger",
                   params={"dataset_id": DATASET_ID, "include_errors": "true"},
                   headers=_headers(),
                   json=[{"url": u} for u in profile_urls])
    if r.status_code >= 300:
        raise EnrichError(f"trigger -> {r.status_code}: {r.text[:200]}")
    snap = (r.json() or {}).get("snapshot_id")
    if not snap:
        raise EnrichError(f"no snapshot_id in trigger response: {r.text[:200]}")

    # 2. poll
    for _ in range(_POLL_MAX):
        with httpx.Client(timeout=_TIMEOUT) as c:
            p = c.get(f"{_BASE}/progress/{snap}", headers=_headers())
        status = (p.json() or {}).get("status") if p.status_code < 300 else None
        if status == "ready":
            break
        if status == "failed":
            raise EnrichError(f"snapshot {snap} failed")
        time.sleep(_POLL_EVERY)
    else:
        _log.error("enrich_timeout", f"snapshot {snap} not ready", metadata={"n": len(profile_urls)})
        return {}

    # 3. download
    with httpx.Client(timeout=_TIMEOUT) as c:
        d = c.get(f"{_BASE}/snapshot/{snap}", params={"format": "json"}, headers=_headers())
    if d.status_code >= 300:
        raise EnrichError(f"snapshot download -> {d.status_code}: {d.text[:200]}")
    records = d.json()
    if not isinstance(records, list):
        records = records.get("data") or []

    out: dict[str, dict[str, str | None]] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        c = _pick_contact(rec)
        if c["profile_url"]:
            out[c["profile_url"]] = {"email": c["email"], "phone": c["phone"],
                                     "name": c["name"], "headline": c["headline"],
                                     "about": c["about"], "company": c["company"]}
    _log.log("enrich_done", metadata={"requested": len(profile_urls), "returned": len(out),
                                      "with_email": sum(1 for v in out.values() if v["email"]),
                                      "with_phone": sum(1 for v in out.values() if v["phone"])})
    return out
