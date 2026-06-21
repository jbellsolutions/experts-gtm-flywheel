# The Expert's GoToMarket Flywheel

### Own your audience. Own your pipeline.

A **self-hosted content + lead engine** that turns what you know into demand — across
the three channels you actually own: **LinkedIn, cold email, and your newsletter.**

The platforms rent you an audience and change the rules whenever they like. Agencies
and bureaus rent you a pipeline and skim every deal. This flips it: a system **you**
run, on **your** accounts, building an audience **you** keep and a pipeline **you**
control. No retainer. No middleman. No rented reach. You own the content, the
contacts, the data, and the machine that makes them — and it runs on about **an hour
a day.**

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

That's the whole install. It takes ~60–90 minutes and you can stop and resume anytime.

---

## What you get

**An entire go-to-market team, in a system you own.**

- **Editorial-grade content that actually sounds like you — and posts itself.**
  One recording (or a single idea) becomes a full week of LinkedIn posts — plus
  Substack, Medium, and a newsletter — each written in *your* voice, wrapped in an
  on-brand image, carousel, or short video, and auto-published at the right time. You
  approve from your phone in minutes. No ghostwriter, no agency retainer, no generic
  AI sludge — your best thinking, at volume.

- **A LinkedIn engagement system that keeps you in front of buyers.**
  Every morning you get the exact posts worth commenting on, each with a sharp comment
  already drafted in your voice. Stay top-of-feed with your market in ten minutes —
  without disappearing into the scroll.

- **One-click lead capture, right in your browser (Chrome + Edge).**
  See a post your buyers are all over? Click once and it goes straight into your
  funnel — no copy-paste, no tab-juggling. A browser extension built for **Chrome and
  Microsoft Edge** (works in any Chromium browser) ships with the system.

- **A lead engine that turns attention into a named pipeline.**
  Drop any LinkedIn post and the system pulls *everyone* who engaged into your
  **Airtable** CRM, finds each person's company and a **verified work email**, and
  writes each one a personal cold email that opens on what they actually care about.
  You go from "that post got likes" to a CRM full of real buyers with real inboxes —
  automatically.

- **Cold-email campaigns that build and send themselves — with SmartLead.**
  The system creates your **SmartLead** campaign for you: your sequence, your
  follow-ups, your schedule. Approve a lead and it drops in, sends, spaces itself out,
  follows up — and **stops the second they reply.** You wake up to conversations, not
  to a CRM you have to work by hand.

- **The whole flywheel — and you own every turn of it.**
  Content earns attention → attention becomes leads → leads become revenue → revenue
  funds more content. It's self-hosted on your own accounts, runs on ~1 hour a day,
  and there's no platform that can switch it off.

It's modular — start with LinkedIn today and switch on the newsletter and the lead
engine whenever you're ready.

---

## What it runs on

Your own accounts (most have generous free tiers). The onboarding assistant sets up
each one and tells you exactly what it's for:

- **Anthropic** — the AI that writes in your voice
- **Airtable** — your lead CRM, where you work every contact
- **SmartLead** — the cold-email sending + follow-up engine
- **Unipile** — publishes to your LinkedIn
- **Railway** — hosts the system
- **Firecrawl · Kit · Browser Use Cloud · enrichment providers** — switched on as you
  turn features on (engagement discovery, newsletter, Substack/Medium, lead enrichment)

Behind the scenes it keeps its own state in a small **Supabase** database + Redis —
plumbing you never touch. Nothing is hardcoded to a vendor you can't swap, and **your
keys live only in `.env.local`, which is never committed.**

---

## How it's built

Three small services on Railway — a Python **worker** that runs the scheduled jobs, a
**browser-runner** that publishes long-form, and a **Next.js dashboard** you operate
it from. Full picture in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Your day, once it's running

About an hour: approve the queued posts, work the engagement list, drop a few good
posts into the lead funnel, and triage the new leads in **Airtable**. The full routine
is in [`docs/OPERATING.md`](docs/OPERATING.md).

---

## Docs

- [`docs/ONBOARDING.md`](docs/ONBOARDING.md) — the guided setup the assistant runs
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how the system works
- [`docs/OPERATING.md`](docs/OPERATING.md) — the daily operator routine
- `.env.example` — every key the system can use, and what each is for

> New here? Don't read these top-to-bottom. Just open the repo in Claude Code and say
> **"set me up."** The assistant takes it from there.
