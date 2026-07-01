# Architecture

A small, self-hosted system: three Railway services, Supabase for state, Redis for
the job queue. Everything is driven by cron jobs in the worker; you operate it from
one dashboard.

```
        recording / idea
              │
              ▼
┌──────────────────────── RAILWAY ────────────────────────┐
│                                                          │
│  worker (Python + croniter)      browser-runner          │
│   • content generation            (Browser Use Cloud)    │
│   • visuals                        publishes Substack /   │
│   • publish scheduler              Medium long-form       │
│   • engagement discovery                                 │
│   • lead-gen drains               dashboard (Next.js)     │
│        │      ▲                    approve + engage +     │
│        ▼      │                    drop posts + status    │
│      Redis (job queue)                                    │
└──────────────────────────────────────────────────────────┘
        │                              │
        ▼                              ▼
   Supabase (state)             External APIs
   drafts · ideas · influencers  Anthropic · Unipile (LinkedIn) ·
   influencer_posts · leadgen_jobs  Kit · Browser Use · Firecrawl ·
   daily_checklists · kv_state    Airtable · SmartLead · SpeakerAgent · enrichment

   Leads live in Airtable (Contacts + Companies), not Supabase.
```

## Services
- **worker** — the brain. Runs every scheduled job (generate content, render visuals,
  publish what's approved, find engagement targets, drain the lead-gen queues). ~50 MB,
  ticks on a cron loop.
- **browser-runner** — a thin Redis consumer that publishes long-form (Substack/Medium)
  through Browser Use Cloud using captured logins. LinkedIn + newsletter publish via API,
  so they don't need this.
- **dashboard** — Next.js 14. The only UI you open: approve drafts, work the engagement
  list, drop posts into the lead funnel, see job status, link out to the Airtable CRM.

## The flow
1. **Content** — `transcript_ingest` pulls a recording; `repurposer` turns it (and
   queued ideas) into drafts in your voice; `visuals` attaches an image/carousel/video;
   `publisher` ships what you approve at set windows.
2. **Engagement** — `influencers` discovers relevant posts via Firecrawl (no LinkedIn
   automation) and drafts a comment in your voice for each → the dashboard's Comments tab.
3. **Leads** — `leadgen.pipeline` scrapes a pasted post's commenters into Airtable, then
   per-row checkboxes (Enrich / Create email / Rerun / Push) run enrichment (Bright Data +
   FullEnrich + a Firecrawl/LLM company lookup), draft the offer email, and push to SmartLead.
4. **Podcasts (optional)** — `dashboard/lib/speakeragent.ts` reads live podcast leads from
   SpeakerAgent, lets the operator request host enrichment + draft generation, and syncs
   status changes back without mirroring the records locally.

## Where the brand lives (what onboarding fills)
- `agents/content_flywheel/repurposer/brand_voice.py` — your voice, pillars, banned phrases,
  few-shot examples. (Plus optional `voice_banks/*.md`.)
- The **offer framework** — editable text in the dashboard (Supabase `app_settings`,
  key `offer_framework:<slug>`); drives the cold email.
- `scripts/smartlead_setup.py` — your cold-email follow-up sequence.
- `docs/SMARTLEAD.md` — SmartLead operating rules and operator workflow.
- `docs/SPEAKERAGENT.md` — podcast lead lane, CLI, and API connection notes.
- `scripts/airtable_setup.py` — builds your lead CRM schema.
- Everything else is generic system code, shared across every brand running this template.

## Config
All secrets come from environment variables (`.env.local` locally; Railway service vars in
production). See `.env.example` for the full list and what each key is for. The system is
modular: unset a provider's key and that feature simply stays off.
