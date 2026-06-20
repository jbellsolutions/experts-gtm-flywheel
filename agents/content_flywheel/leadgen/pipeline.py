"""Lead-gen orchestrator: influencer -> top posts -> commenters -> dedupe -> ICP -> enrich.

Cost-control ordering is the whole point (ScrapeCreators bills per request):

  1. profile()  -> recent posts                              (1 credit / influencer)
  2. for recent posts, get comment counts; keep >= min_comments, take top N.
     A count known from the profile payload skips the /post credit entirely;
     otherwise post() returns count + commenters in one call               (1 credit / examined post)
  3. dedupe commenters on profile_url (within batch + against the DB)
  4. FREE prefilter drops low-signal commenters
  5. profile() each survivor for headline -> ICP score        (1 credit / survivor)  <- real cost driver
  6. Bright Data enriches ONLY the icp_fit leads with email/phone

Every credit-spending step is counted into the job stats — no silent truncation.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.logging.logger import AgentLogger

from . import airtable, apify, company, email_draft, enrich, fullenrich, icp, scrapecreators, smartlead, store
from ..influencers import store as inf_store

# Whose voice the auto-drafted offer emails are written in (organic = your your brand).
EMAIL_VOICE = "ai_guy"

# Free/personal email providers — their domain is NOT a company, so don't derive a
# company from them when Bright Data didn't return one.
_FREE_EMAIL = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
               "msn.com", "yahoo.com", "ymail.com", "icloud.com", "me.com", "aol.com",
               "proton.me", "protonmail.com", "pm.me", "gmx.com", "mail.com"}

_log = AgentLogger("leadgen.pipeline")

DEFAULT_CAPS: dict[str, int | bool] = {
    "top_posts": 5,          # keep at most this many qualifying posts per influencer
    "posts_examined": 12,    # don't look at more than this many recent posts
    "min_comments": 10,      # a post qualifies at >= this many comments
    "max_commenters": 40,    # cap commenters pulled per kept post
    "since_days": 90,        # last 3 months
    "max_enrich": 200,       # cap enrichment calls per batch
    "enrich": True,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ext_id(url: str) -> str:
    tail = url.rstrip("/").split("/")[-1]
    return tail if tail and tail.isalnum() else hashlib.sha1(url.encode()).hexdigest()[:24]


def _within(posted_at: Any, since_days: int) -> bool:
    if not posted_at:
        return True  # unknown date — don't discard
    try:
        dt = datetime.fromisoformat(str(posted_at).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= _now() - timedelta(days=since_days)
    except Exception:  # noqa: BLE001
        return True


def estimate_credits(n_influencers: int, caps: dict | None = None) -> int:
    """Rough up-front ScrapeCreators credit estimate (shown before a crawl runs)."""
    c = {**DEFAULT_CAPS, **(caps or {})}
    per_inf = 1 + c["posts_examined"]                       # profile + examined posts
    commenters = c["top_posts"] * min(c["max_commenters"], 30)
    headline_calls = int(commenters * 0.4)                  # ~prefilter survival rate
    return n_influencers * per_inf + n_influencers * headline_calls


def run_batch(influencer_ids: list[str], caps: dict | None = None) -> dict[str, Any]:
    """Core synchronous pass over the selected influencers. Returns stats."""
    if not scrapecreators.configured():
        raise RuntimeError("SCRAPECREATORS_API_KEY not set — cannot crawl.")

    c = {**DEFAULT_CAPS, **(caps or {})}
    stats = {k: 0 for k in (
        "credits", "posts_examined", "posts_kept", "raw_commenters", "new_leads",
        "prefilter_pass", "icp_fit", "enriched", "with_email", "with_phone")}
    stats["influencers"] = 0

    influencers = store.influencers_by_ids(influencer_ids)
    batch_seen: set[str] = set()
    fresh_leads: list[dict[str, Any]] = []   # {lead_id, profile_url, comment_text}

    for inf in influencers:
        stats["influencers"] += 1
        ident = inf.get("profile_url") or inf.get("handle")
        if not ident:
            continue
        try:
            prof = scrapecreators.profile(ident)
            stats["credits"] += 1
        except Exception as e:  # noqa: BLE001
            _log.error("profile_failed", str(e), metadata={"influencer": ident})
            continue

        kept: list[dict[str, Any]] = []
        for p in scrapecreators.recent_posts(prof):
            if len(kept) >= c["top_posts"] or stats["posts_examined"] >= c["posts_examined"] * len(influencers):
                break
            if not _within(p.get("posted_at"), c["since_days"]):
                continue
            cc = p.get("comment_count")
            if cc is not None and cc < c["min_comments"]:
                continue  # cheap skip — profile told us it's under threshold
            stats["posts_examined"] += 1
            try:
                post_json = scrapecreators.post(p["url"])
                stats["credits"] += 1
            except Exception as e:  # noqa: BLE001
                _log.error("post_failed", str(e), metadata={"url": p["url"]})
                continue
            real_cc = scrapecreators.comment_count(post_json) or (cc or 0)
            if real_cc < c["min_comments"]:
                continue
            cmtrs = scrapecreators.commenters(post_json)[: c["max_commenters"]]
            kept.append({"url": p["url"], "cc": real_cc, "body": p.get("body", ""),
                         "posted_at": p.get("posted_at"), "commenters": cmtrs})

        # store kept posts on the existing influencer_posts table
        for kp in kept:
            stats["posts_kept"] += 1
            try:
                inf_store.upsert_post(
                    influencer_id=inf["id"], platform="linkedin",
                    external_id=_ext_id(kp["url"]), posted_at=kp.get("posted_at"),
                    body=(kp.get("body") or "")[:4000], post_url=kp["url"],
                    comments=kp["cc"], raw={"leadgen": True})
            except Exception as e:  # noqa: BLE001
                _log.error("upsert_post_failed", str(e), metadata={"url": kp["url"]})

        # collect + dedupe commenters
        for kp in kept:
            for cm in kp["commenters"]:
                stats["raw_commenters"] += 1
                url = cm["profile_url"]
                if url in batch_seen:
                    continue
                batch_seen.add(url)
                if store.existing_urls([url]):
                    continue  # already in DB from a prior batch
                lead = store.upsert_lead(
                    profile_url=url, full_name=cm.get("name"),
                    comment_text=cm.get("comment_text"),
                    source_influencer_id=inf["id"], source_post_url=kp["url"],
                    raw={"via": "scrapecreators"})
                stats["new_leads"] += 1
                fresh_leads.append({"lead_id": lead["id"], "profile_url": url,
                                    "comment_text": cm.get("comment_text")})

    # FREE prefilter
    survivors = []
    for ld in fresh_leads:
        ok = icp.prefilter(ld["comment_text"])
        store.set_prefilter(ld["lead_id"], ok)
        if ok:
            survivors.append(ld)
    stats["prefilter_pass"] = len(survivors)

    # headline fetch + ICP score (the real cost driver — survivors only)
    fits: list[dict[str, Any]] = []
    for ld in survivors:
        try:
            prof = scrapecreators.profile(ld["profile_url"])
            stats["credits"] += 1
        except Exception as e:  # noqa: BLE001
            _log.error("headline_failed", str(e), metadata={"url": ld["profile_url"]})
            continue
        hl, ab = scrapecreators.headline(prof), scrapecreators.about(prof)
        fit, score, reason = icp.score_lead(hl, ab)
        store.set_icp(ld["lead_id"], headline=hl, about=ab, fit=fit, score=score, reason=reason)
        if fit:
            fits.append(ld)
    stats["icp_fit"] = len(fits)

    # enrich ICP-fits only
    if c["enrich"] and fits:
        if not enrich.configured():
            _log.log("enrich_skipped", metadata={"reason": "BRIGHT_DATA_API_TOKEN unset", "fits": len(fits)})
            for ld in fits:
                store.mark_enriched(ld["lead_id"], email=None, phone=None, status="queued")
        else:
            target = fits[: c["max_enrich"]]
            try:
                contacts = enrich.enrich([f["profile_url"] for f in target])
            except Exception as e:  # noqa: BLE001
                _log.error("enrich_failed", str(e))
                contacts = {}
            for ld in target:
                ct = contacts.get(ld["profile_url"], {})
                email, phone = ct.get("email"), ct.get("phone")
                got = bool(email or phone)
                store.mark_enriched(ld["lead_id"], email=email, phone=phone,
                                    status="enriched" if got else "failed")
                if got:
                    stats["enriched"] += 1
                if email:
                    stats["with_email"] += 1
                if phone:
                    stats["with_phone"] += 1

    _log.log("batch_done", metadata=stats)
    return stats


# ── paste-a-post mode ──────────────────────────────────────────────────────────

def _handle(url: str) -> str:
    tail = url.rstrip("/").split("/in/")[-1].split("/")[0].split("?")[0]
    return tail or url


def ingest_post(post_url: str) -> dict[str, Any]:
    """Paste-a-post: scrape ONE post -> author + post + ALL commenters -> dedupe ->
    upsert leads. Enrichment + offer-email drafting are MANUAL, per lead (the Leads
    tab 'Enrich' button -> drain_enrich_queue), so we never burn Bright Data /
    FullEnrich credits on commenters the team won't actually work."""
    if not scrapecreators.configured():
        raise RuntimeError("SCRAPECREATORS_API_KEY not set — cannot scrape.")
    stats = {k: 0 for k in ("credits", "commenters", "new_leads")}

    pj = scrapecreators.post(post_url)
    stats["credits"] += 1

    # author -> influencer row
    au = scrapecreators.author(pj)
    inf_id = None
    if au.get("profile_url"):
        try:
            inf = inf_store.upsert_influencer(
                platform="linkedin", handle=_handle(au["profile_url"]),
                profile_url=au["profile_url"], full_name=au.get("name"),
                discovered_via="post_paste", metadata={"followers": au.get("followers")})
            inf_id = inf.get("id")
        except Exception as e:  # noqa: BLE001
            _log.error("upsert_author_failed", str(e), metadata={"url": au.get("profile_url")})

    # the post itself
    pm = scrapecreators.post_meta(pj)
    post_ctx = pm.get("body") or ""
    if inf_id:
        try:
            inf_store.upsert_post(
                influencer_id=inf_id, platform="linkedin", external_id=_ext_id(post_url),
                posted_at=pm.get("posted_at"), body=post_ctx[:4000], post_url=post_url,
                comments=pm.get("comment_count"), raw={"leadgen": True, "via": "post_paste"})
        except Exception as e:  # noqa: BLE001
            _log.error("upsert_post_failed", str(e), metadata={"url": post_url})

    # commenters: Apify (ALL commenters) is primary; ScrapeCreators (~top 10, owned
    # credits) is the fallback when Apify is unconfigured OR yields nothing (e.g. it
    # errored / ran out of usage) — so a dry Apify account never silently means 0 leads.
    cmtrs = apify.commenters(post_url) if apify.configured() else []
    if not cmtrs:
        cmtrs = scrapecreators.commenters(pj)
        if cmtrs:
            _log.log("commenters_fallback", metadata={"source": "scrapecreators", "n": len(cmtrs)})
    # Leads go to the Airtable CRM (Contacts table) when it's configured; otherwise
    # fall back to Supabase lead_contacts so nothing breaks before the base is wired.
    use_airtable = airtable.configured()
    seen: set[str] = set()
    for cm in cmtrs:
        stats["commenters"] += 1
        url = cm["profile_url"]
        if not url or url in seen:
            continue
        seen.add(url)
        if use_airtable:
            rid = airtable.create_if_new({
                airtable.F_NAME: cm.get("name"), airtable.F_URL: url,
                airtable.F_HEADLINE: cm.get("headline"), airtable.F_SAID: cm.get("comment_text"),
                airtable.F_POST: post_url, airtable.F_ENRICH_STATUS: "new"})
            if rid:
                stats["new_leads"] += 1
        elif not store.existing_urls([url]):
            store.upsert_lead(
                profile_url=url, full_name=cm.get("name"), comment_text=cm.get("comment_text"),
                headline=cm.get("headline"), source_influencer_id=inf_id,
                source_post_url=post_url, raw={"via": "post_paste"})
            stats["new_leads"] += 1

    # No auto-enrich / auto-draft. Leads sit un-enriched until the team checks
    # "Enrich" in Airtable (-> drain_airtable), so Bright Data / FullEnrich credits
    # are only spent on chosen leads.
    _log.log("post_ingest_done", metadata={**stats, "post_url": post_url, "sink": "airtable" if use_airtable else "supabase"})
    return stats


# ── cron entrypoints ───────────────────────────────────────────────────────────

async def drain_jobs() -> None:
    """Cron (*/2 min) — run the oldest queued job (post-paste OR influencer crawl)."""
    job = store.claim_next_job()
    if not job:
        return
    caps = job.get("caps") or {}
    mode = caps.get("mode")
    _log.log("job_start", metadata={"job_id": job["id"], "mode": mode or "influencer"})
    try:
        if mode == "post":
            stats = ingest_post(caps.get("post_url"))
        else:
            stats = run_batch(job.get("influencer_ids") or [], caps)
        store.finish_job(job["id"], status="done", stats=stats)
    except Exception as e:  # noqa: BLE001
        _log.error("job_failed", str(e), metadata={"job_id": job["id"]})
        store.finish_job(job["id"], status="failed", error=str(e)[:500])


async def drain_enrich_queue() -> None:
    """Cron (*/3 min) — the Leads-tab "Enrich" button. For each lead the team
    flagged (enrichment_status='queued'): Bright Data company/title + FullEnrich
    verified work email + a drafted offer email in the lead's chosen voice + offer
    (both ride in lead.raw, captured at click time). Credits are only spent here —
    on the leads the team picked, never on the whole commenter list."""
    rows = store.queued_for_enrich(25)
    if not rows:
        return

    # Bright Data → company / headline / about (chunked, best-effort).
    profiles: dict = {}
    if enrich.configured():
        try:
            profiles = enrich.enrich([r["profile_url"] for r in rows])
        except Exception as e:  # noqa: BLE001
            _log.error("enrich_queue_bd_failed", str(e))
    for r in rows:
        p = profiles.get(r["profile_url"], {}) or {}
        r["_company"], r["_headline"], r["_about"] = p.get("company"), p.get("headline"), p.get("about")

    # FullEnrich → verified work email (emails only; the decided contact source).
    emails: dict = {}
    if fullenrich.configured():
        res = fullenrich.enrich_bulk(
            [{"full_name": r.get("full_name"), "company": r.get("_company"),
              "linkedin_url": r["profile_url"], "lead_id": r["id"]} for r in rows])
        if "__error__" in res:
            _log.error("enrich_queue_fe_failed", res["__error__"])
        else:
            emails = res

    drafted = 0
    for r in rows:
        em = (emails.get(r["id"], {}) or {}).get("email")
        got = bool(r.get("_headline") or r.get("_about"))
        store.mark_enriched(r["id"], email=em, phone=None,
                            status="enriched" if (em or got) else "failed",
                            headline=r.get("_headline"), about=r.get("_about"))
        # Draft the offer email in the lead's chosen voice + offer (defaults if unset).
        raw = r.get("raw") or {}
        voice = raw.get("draft_voice") or EMAIL_VOICE
        framework = store.offer_framework(raw.get("draft_offer") or "ai_integraterz")
        d = email_draft.draft_email(
            lead={"name": r.get("full_name"), "headline": r.get("_headline"),
                  "about": r.get("_about"), "comment_text": r.get("comment_text")},
            framework=framework, voice=voice)
        if d:
            store.set_email_draft(r["id"], subject=d.get("subject"), body=d.get("body"), status="drafted")
            drafted += 1
        else:
            store.set_email_draft(r["id"], subject=None, body=None, status="failed")

    _log.log("enrich_queue_done", metadata={
        "count": len(rows), "drafted": drafted,
        "with_email": sum(1 for r in rows if (emails.get(r["id"], {}) or {}).get("email"))})


async def drain_airtable() -> None:
    """Cron — act on the Airtable CRM's per-row checkboxes (leads live in Airtable
    now, not the dashboard). Enrich → Bright Data company + FullEnrich email;
    Create email / Rerun → draft the offer email in the row's Voice + Offer (Rerun
    applies the Feedback box). Each action clears its checkbox. No-op until
    AIRTABLE_API_KEY + AIRTABLE_BASE_ID are set."""
    if not airtable.configured():
        return

    # 1. ENRICH (batched): Bright Data company + FullEnrich verified email.
    recs = airtable.flagged(airtable.F_ENRICH)
    if recs:
        urls = [r["fields"].get(airtable.F_URL) for r in recs if r["fields"].get(airtable.F_URL)]
        profiles: dict = {}
        if urls and enrich.configured():
            try:
                profiles = enrich.enrich(urls)
            except Exception as e:  # noqa: BLE001
                _log.error("airtable_enrich_bd", str(e))
        emails: dict = {}
        if fullenrich.configured():
            res = fullenrich.enrich_bulk([
                {"full_name": r["fields"].get(airtable.F_NAME),
                 "company": (profiles.get(r["fields"].get(airtable.F_URL), {}) or {}).get("company"),
                 "linkedin_url": r["fields"].get(airtable.F_URL), "lead_id": r["id"]}
                for r in recs if r["fields"].get(airtable.F_URL)])
            if "__error__" in res:
                _log.error("airtable_enrich_fe", res["__error__"])
            else:
                emails = res
        co_cache: dict[str, str | None] = {}
        for r in recs:
            f = r["fields"]
            p = profiles.get(f.get(airtable.F_URL), {}) or {}
            em = (emails.get(r["id"], {}) or {}).get("email")
            comp = p.get("company") or f.get(airtable.F_COMPANY)
            comp_domain = None
            # Bright Data often lacks the company; the verified work email reveals
            # it. Derive the company (name + domain) from a non-free email domain.
            if not comp and em and "@" in em:
                dom = em.rsplit("@", 1)[-1].lower().strip()
                if dom and dom not in _FREE_EMAIL:
                    comp_domain = dom
                    comp = dom.split(".")[0].replace("-", " ").title()
            upd: dict[str, Any] = {airtable.F_ENRICH: False, airtable.F_EMAIL: em or "",
                                   airtable.F_ENRICH_STATUS: "enriched" if (em or comp or p.get("headline")) else "no contact"}
            if em:
                upd[airtable.F_EMAIL_STATUS] = "found"
            if comp:
                upd[airtable.F_COMPANY] = comp
            if p.get("headline"):
                upd[airtable.F_HEADLINE] = p["headline"]
            airtable.patch_contact(r["id"], upd)
            # Phase 2: ensure + enrich the company (Firecrawl + LLM, deduped per
            # batch) and link the contact to it. domain_hint skips the Firecrawl
            # search when the email already told us the domain.
            if comp:
                _ensure_company(comp, r["id"], co_cache, domain_hint=comp_domain)
        _log.log("airtable_enrich_done", metadata={"count": len(recs),
                 "with_email": sum(1 for r in recs if (emails.get(r["id"], {}) or {}).get("email"))})

    # 2. CREATE EMAIL, 3. RERUN (with feedback) — both draft via email_draft.
    for rec in airtable.flagged(airtable.F_CREATE):
        _airtable_draft(rec, flag=airtable.F_CREATE)
    for rec in airtable.flagged(airtable.F_RERUN):
        _airtable_draft(rec, flag=airtable.F_RERUN,
                        feedback=(rec["fields"].get(airtable.F_FEEDBACK) or "").strip() or None)

    # 4. COMPANIES: (re)enrich any Companies row whose Enrich box is checked.
    for rec in airtable.flagged_companies():
        name = (rec.get("fields") or {}).get(airtable.CO_NAME)
        info = company.enrich(name) if (name and company.configured()) else None
        cupd: dict[str, Any] = {airtable.CO_ENRICH: False}
        if info:
            cupd.update({airtable.CO_DOMAIN: info.get("domain") or "",
                         airtable.CO_WEBSITE: info.get("website") or "",
                         airtable.CO_INDUSTRY: info.get("industry") or "",
                         airtable.CO_SIZE: info.get("size") or "",
                         airtable.CO_SUMMARY: info.get("summary") or "",
                         airtable.CO_STATUS: "enriched"})
        airtable.patch_company(rec["id"], cupd)

    # 5. PUSH TO CAMPAIGN (Phase 3): add drafted + emailed contacts to the BDR's
    # SmartLead campaign. The campaign sequence merges the {{email_subject}} /
    # {{email_body}} custom fields, so each lead sends its own drafted offer email.
    if smartlead.configured():
        camp = smartlead.default_campaign()
        for rec in airtable.flagged(airtable.F_PUSH):
            f = rec["fields"]
            email, body = f.get(airtable.F_EMAIL), f.get(airtable.F_BODY)
            ok, why = False, ""
            if not email:
                why = "no email"
            elif not body:
                why = "no drafted email"
            elif not camp:
                why = "no SMARTLEAD_CAMPAIGN_ID set"
            else:
                res = smartlead.add_lead(camp, email=email, full_name=f.get(airtable.F_NAME),
                                         company=f.get(airtable.F_COMPANY), subject=f.get(airtable.F_SUBJECT),
                                         body=body, linkedin_url=f.get(airtable.F_URL))
                ok, why = bool(res.get("ok")), (res.get("error") or "")
            if not ok:
                _log.error("airtable_push_failed", why, metadata={"contact": rec["id"]})
            # Fixed single-select values only (no dynamic error text → no junk options).
            airtable.patch_contact(rec["id"], {airtable.F_PUSH: False,
                                               airtable.F_EMAIL_STATUS: "in campaign" if ok else "push failed"})


def _ensure_company(name: str, contact_id: str, cache: dict, domain_hint: str | None = None) -> None:
    """Upsert the Companies row, enrich it once (Firecrawl + LLM, best-effort),
    and link the contact. `cache` dedupes companies within a drain batch;
    `domain_hint` (from the email) skips the Firecrawl domain search."""
    cid = cache.get(name, "__miss__")
    if cid == "__miss__":
        cid, already = airtable.upsert_company(name)
        cache[name] = cid
        if cid and not already and company.configured():
            info = company.enrich(name, domain=domain_hint)
            if info:
                airtable.patch_company(cid, {
                    airtable.CO_DOMAIN: info.get("domain") or "",
                    airtable.CO_WEBSITE: info.get("website") or "",
                    airtable.CO_INDUSTRY: info.get("industry") or "",
                    airtable.CO_SIZE: info.get("size") or "",
                    airtable.CO_SUMMARY: info.get("summary") or "",
                    airtable.CO_STATUS: "enriched"})
    if cid and contact_id:
        airtable.link_contact_company(contact_id, cid)


def _airtable_draft(rec: dict, *, flag: str, feedback: str | None = None) -> None:
    """Draft (or re-draft) the offer email for one Airtable Contacts row, in its
    chosen Voice + Offer, then clear the triggering checkbox."""
    f = rec.get("fields", {})
    voice = airtable.VOICE_LABEL_TO_ID.get(f.get(airtable.F_VOICE), EMAIL_VOICE)
    offer = airtable.OFFER_LABEL_TO_SLUG.get(f.get(airtable.F_OFFER), "ai_integraterz")
    d = email_draft.draft_email(
        lead={"name": f.get(airtable.F_NAME), "headline": f.get(airtable.F_HEADLINE),
              "about": None, "comment_text": f.get(airtable.F_SAID)},
        framework=store.offer_framework(offer), voice=voice, feedback=feedback)
    upd: dict[str, Any] = {flag: False}
    if flag == airtable.F_RERUN:
        upd[airtable.F_FEEDBACK] = ""  # feedback consumed
    if d:
        upd[airtable.F_SUBJECT] = d.get("subject") or ""
        upd[airtable.F_BODY] = d.get("body") or ""
        upd[airtable.F_EMAIL_STATUS] = "drafted"
    else:
        upd[airtable.F_EMAIL_STATUS] = "draft failed"
    airtable.patch_contact(rec["id"], upd)


async def run_scheduled() -> None:
    """Weekly pass over all tracked influencers. NOT wired into JOBS yet —
    you flips this on once the on-demand path proves out cost + quality."""
    ids = [i["id"] for i in inf_store.list_tracked("linkedin", limit=100)]
    if not ids:
        return
    stats = run_batch(ids, DEFAULT_CAPS)
    _log.log("scheduled_done", metadata=stats)


if __name__ == "__main__":
    import asyncio
    asyncio.run(drain_jobs())
