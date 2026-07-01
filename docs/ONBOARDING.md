# Onboarding Script

This is the playbook the onboarding assistant follows (see `CLAUDE.md`). Run it
**one stage at a time, conversationally.** Do the work for the user (edit files, run
scripts, call APIs) on their approval. Keep a visible checklist of stages done /
remaining. Secrets only ever go in `.env.local`.

The flow is **modular** — LinkedIn content is the core; engagement, the newsletter,
and the lead engine are add-ons. If the user only wants part of it today, set that
part up and skip the rest (you can always come back).

---

## Stage 0 — Welcome (your first message)
**Goal:** orient + earn trust, then ask one question.
- One paragraph: what The Expert's GoToMarket Flywheel is (own your audience + pipeline
  across LinkedIn, cold email, newsletter; ~1 hr/day to run).
- Expectations: step by step, ~60–90 min, you do the setup with them, they can stop/resume.
- Ask **one** thing: *"Tell me about you — who are you, what do you do, and who do you help?"*

## Stage 1 — Discovery (learn the brand)
**Goal:** capture enough to generate their voice + offer. Ask in 2–4 short rounds, not all at once:
1. Who they are + the experience that earns them authority.
2. Who they help (ICP) + the outcome they create.
3. Their offer(s) — what they sell, the core promise, the proof.
4. Voice/tone — or ask for 2–3 of their best existing posts and infer it.
5. Channels they want on day one (LinkedIn always; + newsletter? + cold email/leads?).

Write the captured profile to `docs/your-brand.md` (a scratch file, gitignored is fine)
so it survives a resume. Reflect it back: *"Here's what I heard — correct anything."*

## Stage 2 — Generate the brand (you write the files)
**Goal:** turn the interview into the system's brand config. Draft, show, get edits, then write:
- `agents/content_flywheel/repurposer/brand_voice.py` → fill `VOICE_DOC`, `PILLAR_1_HOOKS`,
  `PILLAR_2_BEATS`, and `BANNED_PHRASES` from the interview. If they gave sample posts, paste
  2–5 into `FEW_SHOT_LINKEDIN` (tagged 1/2). (Optionally fill the primary `voice_banks/ai_guy.md`.)
- Offer framework text → you'll store it in the dashboard later (Supabase `app_settings`,
  key `offer_framework:your_offer`); for now keep it in `docs/your-brand.md`.
- Cold-email follow-ups → draft 4 in their voice; you'll paste them into
  `scripts/smartlead_setup.py` (E2A–E4A) before creating the campaign.
Always show drafts and let them edit — this is *their* voice going out.

## Stage 3 — Accounts & keys (collect into `.env.local`)
**Goal:** gather only the keys for the channels they chose. For each: one line on what it's
for + the link, then have them paste it; you write it to `.env.local`. Copy `.env.example`
→ `.env.local` first. Group by need:

**Core (always):**
- `ANTHROPIC_API_KEY` — the AI that writes in their voice. console.anthropic.com
- `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` — the database (free). supabase.com
- `FIRECRAWL_API_KEY` — safe discovery of posts/people (no LinkedIn login). firecrawl.dev

**LinkedIn publishing:** `UNIPILE_API_KEY` + `UNIPILE_DSN` + `UNIPILE_LINKEDIN_ACCOUNT_ID` — unipile.com
**Newsletter (optional):** `CONVERTKIT_API_KEY` (Kit). kit.com
**Substack/Medium (optional):** `BROWSER_USE_API_KEY` + captured profiles. cloud.browser-use.com
**Lead engine (optional):** `AIRTABLE_API_KEY` + `AIRTABLE_BASE_ID` (airtable.com),
  `APIFY_TOKEN` (apify.com), `SCRAPECREATORS_API_KEY` (scrapecreators.com),
  `FULLENRICH_API_KEY` (fullenrich.com), `BRIGHTDATA_API_TOKEN` (brightdata.com, optional),
  `SMARTLEAD_API_KEY` + `SMARTLEAD_CAMPAIGN_ID` (smartlead.ai)
**SpeakerAgent (optional):** `SPEAKERAGENT_API_URL` + `SPEAKERAGENT_API_KEY` +
  `SPEAKERAGENT_SPEAKER_ID`
**Ops:** `SLACK_BOT_TOKEN` + `SLACK_OPERATOR_USER_ID` for the morning brief (optional).

## Stage 4 — Database + deploy
**Goal:** stand up the infrastructure.
- **Supabase:** create the project, then run the migrations: `python scripts/run_supabase_migration.py`
  (point it at their `SUPABASE_*`). Confirm the tables exist.
- **Railway:** deploy the three services (worker, browser-runner, dashboard) + a Redis plugin
  from this repo. Set the env from `.env.local` on each service. (Walk them through the Railway
  UI or the `railway` CLI; confirm each build goes green.) The dashboard needs `AIRTABLE_BASE_ID`
  too (for the "Open in Airtable" link).

## Stage 5 — Lead CRM + campaign (only if doing leads)
- **Airtable:** they create a **new blank base** (you can't — the API can't create bases).
  Get the base id → set `AIRTABLE_BASE_ID` → run `python scripts/airtable_setup.py --base <id>`
  (builds Contacts + Companies). Rename the Voice/Offer single-select options to theirs.
- **SmartLead:** paste the drafted follow-ups into `scripts/smartlead_setup.py`, then
  `python scripts/smartlead_setup.py --create --name "<Brand> Outreach"` → set the printed
  `SMARTLEAD_CAMPAIGN_ID`. **They** add their sender inboxes + **START** the campaign (you can't).
  Also walk them through `docs/SMARTLEAD.md` so they know the operating rules and guardrails.

## Stage 6 — Connect channels
- **LinkedIn:** connect their account in Unipile; confirm `UNIPILE_LINKEDIN_ACCOUNT_ID`.
- **Substack/Medium (optional):** capture each login in the Browser Use Cloud dashboard;
  set `BU_PROFILE_SUBSTACK` / `BU_PROFILE_MEDIUM`.
- **Newsletter (optional):** confirm Kit key; `NEWSLETTER_AUTOSEND` stays `false` until they've
  seen one issue as a Kit draft.
- **SpeakerAgent (optional):** connect `SPEAKERAGENT_API_URL`, `SPEAKERAGENT_API_KEY`,
  and `SPEAKERAGENT_SPEAKER_ID`; confirm the `SpeakerAgent` dashboard tab loads podcast leads.

## Stage 7 — First run + verify
- Generate a first batch of content (or repurpose a recording) → confirm drafts appear on the
  dashboard in their voice.
- If leads: have them paste one post URL in the Leads tab → confirm contacts land in Airtable →
  set Enrich + Create email on one → confirm a personalized email drafts in their voice.
- Fix anything that didn't render right *with* them.

## Stage 8 — Hand off
- Walk them through `docs/OPERATING.md` (the ~1-hour daily routine: approve drafts → engage →
  feed the lead funnel → work the CRM).
- Recap what's live, what's optional/next (e.g. start the SmartLead campaign, turn on newsletter
  autosend once they've reviewed an issue), and how to re-open you anytime to add a channel.

---

### Resuming
If the session restarts, read `docs/your-brand.md` and `.env.local` to see how far you got,
tell the user where you left off, and continue from the next unfinished stage.
