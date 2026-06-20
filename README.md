# The Expert's GoToMarket Flywheel

**Own your audience. Own your pipeline.**

A self-hosted go-to-market engine for experts. It turns what you know into a
compounding flywheel across the three channels you actually own — **LinkedIn,
cold email, and a newsletter** — and runs on about **one hour a day**.

No agency. No bureau. No rented audience. You own the content, the contacts, the
data, and the system.

---

## What makes this different: it sets *itself* up

You don't need to be technical. **Drop this repo into [Claude Code](https://claude.com/claude-code)
or Codex and say "set me up."** An onboarding assistant introduces itself, learns
about you and your offer in a short interview, writes your brand voice, walks you
through connecting your accounts, deploys the system, and hands you your daily
routine — one step at a time, doing the work with you.

```
1. Open this folder in Claude Code (or Codex)
2. Say:  set me up
3. Answer its questions + paste a few API keys when asked
```

That's the whole install. It takes ~60–90 minutes and you can stop and resume
anytime.

---

## What you get

- **Content engine** — turn one recording (or a single idea) into a week of
  LinkedIn posts, plus optional Substack, Medium, and a newsletter — all written
  in *your* voice, all approved by you from one mobile-friendly dashboard.
- **Auto visuals** — every post gets an on-brand image, carousel, or short video.
- **Engagement list** — a daily set of the right posts to comment on, each with a
  comment pre-drafted in your voice. You stay top-of-feed without the doomscroll.
- **Lead engine** — paste any post; the system pulls everyone who engaged with it
  into an **Airtable CRM**, enriches them (company + verified email), drafts a
  personalized cold email in your voice, and pushes it into a **SmartLead**
  campaign that sends and follows up. Replies come to your inbox.

It's modular — start with LinkedIn today and switch on the newsletter and the
lead engine whenever you're ready.

## What it runs on

Your own accounts (most have free tiers): Anthropic (the AI), Supabase (database),
Railway (hosting), Unipile (LinkedIn), and — as you turn features on — Firecrawl,
Kit, Browser Use Cloud, Airtable, SmartLead, and a couple of enrichment providers.
The onboarding assistant walks you through each one and tells you what it's for.

Nothing is hardcoded to a vendor you can't replace, and **your keys live only in
`.env.local`, which is never committed.**

## How it's built

Three small services on Railway (a Python **worker** that runs the cron jobs, a
**browser-runner** that publishes long-form, and a **Next.js dashboard**), with
Supabase for state and Redis for the job queue. Full picture in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Your day, once it's running

About an hour: approve the queued posts, work the engagement list, drop a few good
posts into the lead funnel, and triage the new leads in Airtable. The full routine
is in [`docs/OPERATING.md`](docs/OPERATING.md).

---

## Docs

- [`docs/ONBOARDING.md`](docs/ONBOARDING.md) — the guided setup the assistant runs
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how the system works
- [`docs/OPERATING.md`](docs/OPERATING.md) — the daily operator routine
- `.env.example` — every key the system can use, and what each is for

> New here? Don't read these top-to-bottom. Just open the repo in Claude Code and
> say **"set me up."** The assistant takes it from there.
