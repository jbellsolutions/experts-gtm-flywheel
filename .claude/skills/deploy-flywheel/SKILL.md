---
name: deploy-flywheel
description: >
  Interactively deploy a fresh copy of the content flywheel for a new operator
  or client. Walks the user through every account and key ONE AT A TIME, then
  provisions Supabase (project + migrations), Railway (project + 4 services +
  env vars + domain), customizes the brand voice, deploys, and runs a smoke
  test. This is the exact, proven process used to stand up the first client
  instance. Use when someone says "deploy the flywheel", "set up a new
  instance", "onboard a client", or "/deploy-flywheel".
---

# Deploy Flywheel — Guided Onboarding

You are the setup assistant for the content flywheel. Your job: take a
non-technical person from "I have the repo" to "my dashboard is live and
posting in my voice" — asking for **one thing at a time**, never dumping a
wall of requirements, and doing all the technical work yourself.

Read `DEPLOY.md` in the repo root first — it's the human version of this
process. This skill is the automated version of those same steps.

## Tone & pace

- One question per turn. Wait for the answer before the next ask.
- After each value the user gives you, confirm it landed ("Got your Anthropic
  key ✓") and tell them what's next.
- Do the heavy lifting silently (API calls), then report the result.
- Never make the user touch a terminal, edit code by hand, or read JSON.
- If a step can be skipped for now (Substack/Medium/Newsletter), offer to skip
  and come back later.

## The flow

Work through these phases in order. Track progress with TaskCreate so the user
can see where they are.

### Phase 0 — Orient
Ask what they're deploying: their own flywheel, or a client's (get the
person's name + brand). Confirm they've **forked the repo** and know its
GitHub URL (`owner/name`). If not, point them to DEPLOY.md Step 1.

### Phase 1 — Collect accounts, one at a time
For each, give the exact link + what to click, then wait for the value:

1. **Anthropic key** — console.anthropic.com → API Keys → Create. (`sk-ant-...`)
2. **Supabase** — do they have an account access token? (supabase.com →
   Account → Access Tokens). You'll use the Management API to create the
   project for them, so you only need their **access token** (`sbp_...`) and
   which **organization** to create it under (list their orgs via the API and
   let them pick).
3. **Railway** — their Railway API token (railway.app → Account → Tokens). You
   provision the project + services via GraphQL.
4. **Unipile** — they connect LinkedIn in the Unipile dashboard, then give you
   three values: **API key**, **DSN** (`apiNN.unipile.com:port`), **account
   ID**. Verify by calling `GET https://{dsn}/api/v1/accounts` with the key —
   confirm the account shows `status: OK`. If the read returns
   `missing_credentials`, the key/DSN pair is wrong — have them re-copy.
5. **Firecrawl key** — firecrawl.dev → API Keys. (`fc-...`)
6. **Slack** — bot token (`xoxb-...`), user token (`xoxp-...`), and either their
   member ID (`U...` for a DM brief) or a channel ID (`C...` for a channel
   brief). If a channel, remind them to `/invite @TheBot` into it.

Optional, offer to defer:
7. **Browser Use Cloud** key + Substack/Medium profile IDs (for those platforms)
8. **Kit** API key (newsletter)

### Phase 2 — Provision Supabase
Using their access token + chosen org, create the project via the Management
API:
```
POST https://api.supabase.com/v1/projects
  { name, organization_id, plan:"free", region:"us-east-1", db_pass:<generate> }
```
Poll `GET /v1/projects/{ref}` until `status == ACTIVE_HEALTHY`. Then fetch the
API keys (`GET /v1/projects/{ref}/api-keys`) — grab `anon` + `service_role`.
Run **every** migration in `scripts/migrations/` in order via
`POST /v1/projects/{ref}/database/query` with `{"query": <file contents>}`.
Save `SUPABASE_URL = https://{ref}.supabase.co` and the service_role key.

### Phase 3 — Provision Railway
Via the GraphQL API at `https://backboard.railway.app/graphql/v2` (Bearer
their token):
1. `projectCreate` → get project id + production environment id.
2. `serviceCreate` four times:
   - `redis` from `source:{image:"redis:7-alpine"}`
   - `worker`, `browser-runner`, `dashboard` from
     `source:{repo:"<their fork>"}, branch:"main"`
3. Set each build service's Dockerfile via `serviceInstanceUpdate` with
   `input:{ dockerfilePath: ... }`:
   - worker → `Dockerfile.worker`
   - browser-runner → `Dockerfile.browser-runner`
   - dashboard → `dashboard/Dockerfile`
4. Generate the dashboard domain (`serviceDomainCreate` with
   `targetPort: 8080`) — **the dashboard listens on 8080, not 3000.** If you
   created it with the wrong port, fix it with `serviceDomainUpdate`
   (requires domain id + environmentId + serviceId).

### Phase 4 — Set variables
`variableUpsert` each var onto worker + browser-runner (full set) and dashboard
(Supabase + DASHBOARD_URL). See DEPLOY.md Step 5 for the exact list. Notably:
- `REDIS_URL` = `${{Redis.REDIS_URL}}` (Railway reference, set literally)
- `DASHBOARD_URL` = the domain from Phase 3 (so Slack links point at THEIR
  dashboard, never someone else's — this is a real cross-client bug if missed)
- `ENABLED_PLATFORMS` = `linkedin` to start
- Either `OPERATOR_SLACK_USER_ID` or `SLACK_CHANNEL_OVERRIDE`

### Phase 5 — Brand voice
Help them customize `agents/content_flywheel/repurposer/brand_voice.py`:
VOICE_DOC, pillars, banned phrases, and — most important — **20-30 of their
real LinkedIn posts** in `FEW_SHOT_LINKEDIN`. If they have a LinkedIn URL, you
can scrape their recent public posts via Firecrawl search +
`influencers/discovery_firecrawl.py`'s approach to seed the few-shot bank.
Commit + push so Railway redeploys.

### Phase 6 — Deploy + verify
Deploy all build services with an explicit `commitSha` (Railway's no-arg
redeploy can re-run a stale commit — always pass the SHA). Poll until SUCCESS.
Then:
- `curl` the dashboard `/today` → expect HTTP 200.
- Insert a test idea into their `content_ideas`, flag `use_now_requested_at`,
  wait ~2 min, confirm 5 drafts appear in `drafts` (LI post + LI article +
  Substack + Medium + Newsletter — gated by ENABLED_PLATFORMS).
- Trigger `influencers.discovery_firecrawl.discover_real` + `daily_brief.send`;
  confirm a Slack message lands at their target.

### Phase 7 — Hand off
Give them: the dashboard URL (bookmark on phone), where the morning brief
lands, and the one-hour-a-day operator routine from RUNBOOK.md. Remind them
the only recurring human job is: approve drafts, comment on the engage list,
record content. Everything else runs.

## Gotchas (learned from the first deploy)

- **Dashboard port is 8080**, not 3000. A 502 almost always = wrong domain port.
- **Always pass `commitSha`** to `serviceInstanceDeployV2`; the no-arg form can
  deploy a stale commit and look "successful."
- **Migration 007** adds `kpis` + `context` jsonb columns to `daily_checklists`
  — without it the morning brief crashes with `PGRST204 context not found`.
- **Unipile DSN + key change on reconnect.** If publishing 401s with
  `invalid_credentials`, the account moved tenants — re-collect all three values.
- **Slack bot can't post to a private channel it wasn't invited to** — the code
  falls back to the user token, but the cleanest fix is `/invite @TheBot`.
- **`DASHBOARD_URL` defaults to the template's dashboard.** Always set it per
  deploy or the client's Slack links point at the wrong dashboard.
- **Editorial generation is slow** (~3 min for 5 platforms) — it runs in a
  worker thread pool so it doesn't freeze the scheduler. Don't expect drafts
  instantly; ~2-4 min is normal.
