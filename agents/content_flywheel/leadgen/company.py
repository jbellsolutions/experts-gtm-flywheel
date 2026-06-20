"""Company enrichment for the Airtable Companies table (Phase 2).

Given a company NAME (Bright Data gives us the name on a Contact), find its
domain via Firecrawl search, scrape the homepage, and have the shared LLM router
summarize industry / size / what-they-do. Firecrawl + our own LLM only — no paid
enrichment SaaS. Config: FIRECRAWL_API_KEY (already on the worker).
"""
from __future__ import annotations

import json
import os
from urllib.parse import urlparse

import httpx

from shared.logging.logger import AgentLogger

from ..repurposer.llm import complete

_log = AgentLogger("leadgen.company")

_SEARCH = "https://api.firecrawl.dev/v1/search"
_SCRAPE = "https://api.firecrawl.dev/v1/scrape"
_TIMEOUT = 45
# Not a company's own site — skip these when picking a domain from search results.
_SKIP = ("linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
         "youtube.com", "tiktok.com", "crunchbase.com", "wikipedia.org", "glassdoor.com",
         "indeed.com", "github.com", "medium.com", "g2.com", "bloomberg.com", "reddit.com")


def configured() -> bool:
    return bool(os.getenv("FIRECRAWL_API_KEY"))


def _key() -> str:
    return os.getenv("FIRECRAWL_API_KEY", "")


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"}


def _domain(url: str) -> str | None:
    u = (url or "").strip()
    if not u:
        return None
    if not u.startswith("http"):
        u = "https://" + u
    host = urlparse(u).netloc.lower().removeprefix("www.")
    return host.split(":")[0] if "." in host else None


def find_domain(company_name: str) -> str | None:
    """Firecrawl search '<company> official website' → first real (non-social) domain."""
    if not configured() or not company_name:
        return None
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.post(_SEARCH, headers=_headers(),
                       json={"query": f"{company_name} official website", "limit": 6})
        results = (r.json() or {}).get("data") or [] if r.status_code < 300 else []
    except Exception as e:  # noqa: BLE001
        _log.error("company_search_failed", str(e), metadata={"company": company_name[:60]})
        return None
    for item in results:
        d = _domain(item.get("url", ""))
        if d and not any(s in d for s in _SKIP):
            return d
    return None


def _scrape(domain: str) -> str:
    try:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.post(_SCRAPE, headers=_headers(),
                       json={"url": f"https://{domain}", "formats": ["markdown"]})
        if r.status_code < 300:
            return ((r.json() or {}).get("data") or {}).get("markdown") or ""
        _log.error("company_scrape_http", f"{r.status_code}: {r.text[:120]}", metadata={"domain": domain})
    except Exception as e:  # noqa: BLE001
        _log.error("company_scrape_failed", str(e), metadata={"domain": domain})
    return ""


def _parse(raw: str) -> dict:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = s.split("```")[1]
        if s.startswith("json"):
            s = s[4:]
    try:
        d = json.loads(s.strip())
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


_SYS = (
    "You research B2B companies. From the company name + scraped homepage text, return "
    "STRICT JSON only (no markdown): "
    '{"industry":"<short industry>","size":"<one of: 1-10, 11-50, 51-200, 201-1000, 1000+ or \\"\\">",'
    '"summary":"<2-3 sentence plain description of what they do + who they serve>"}. '
    "If the text is thin, infer conservatively from the name; never invent specifics like "
    "headcount or funding."
)


def enrich(company_name: str, domain: str | None = None) -> dict | None:
    """{name, domain, website, industry, size, summary} for the company, or None.
    `domain` (e.g. derived from a verified work email) skips the Firecrawl search
    and scrapes that site directly."""
    if not company_name and not domain:
        return None
    domain = domain or find_domain(company_name)
    company_name = company_name or (domain.split(".")[0].title() if domain else "")
    text = _scrape(domain) if domain else ""
    data: dict = {}
    try:
        data = _parse(complete("company_enrich", _SYS,
                               f"COMPANY: {company_name}\nDOMAIN: {domain or '(unknown)'}\n\n"
                               f"HOMEPAGE TEXT:\n{text[:8000]}"))
    except Exception as e:  # noqa: BLE001
        _log.error("company_llm_failed", str(e), metadata={"company": company_name[:60]})
    out = {
        "name": company_name,
        "domain": domain,
        "website": f"https://{domain}" if domain else None,
        "industry": (data.get("industry") or "").strip() or None,
        "size": (data.get("size") or "").strip() or None,
        "summary": (data.get("summary") or "").strip() or None,
    }
    _log.log("company_enriched", metadata={"company": company_name[:60], "domain": domain,
                                           "has_summary": bool(out["summary"])})
    return out
