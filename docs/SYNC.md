# Keeping the template in sync with your internal builds

You run real brand deployments of this system (your own; and any you build for
clients). Those are where you actually develop and battle-test improvements. This
public template is the **shareable core** — the same system, with all brand and
secret content replaced by placeholders that the onboarding assistant fills.

## The model

```
  internal brand build (source of truth for SYSTEM code)
            │   scripts/sync_from_internal.sh
            ▼
  this template  ──(clone + onboarding)──►  a new user's brand deployment
```

- **System code** (the leadgen pipeline, publisher, visuals, dashboard, workers,
  scheduler, Dockerfiles) lives once and flows **internal → template**.
- **Brand/template files** are *owned by the template* and never overwritten by a
  sync, because each deployment fills them differently:
  - `agents/content_flywheel/repurposer/brand_voice.py`
  - `agents/content_flywheel/repurposer/voices.py` + `voice_banks/`
  - `dashboard/lib/leadgen-offers.ts`, `dashboard/app/leads/page.tsx`
  - `scripts/smartlead_setup.py`, `scripts/airtable_setup.py`
  - `CLAUDE.md`, `AGENTS.md`, `README.md`, `docs/`, `.env*`

## Running a sync

When you ship a system improvement on your internal build, propagate it:

```bash
scripts/sync_from_internal.sh /path/to/your-internal-repo
```

This:
1. Pulls the **system** paths in (skipping the template-owned files above).
2. Runs `scripts/_scrub_template.py` — replaces hard-coded IDs/URLs with placeholders
   and rewrites brand-person phrasing generically.
3. **Leak-checks** — fails loudly if any brand name or secret pattern survives.

Then **review `git diff`**, commit, and push. The diff is your final gate before
anything ships to the public repo.

## Limitations (V1)

- The sync brings *behavioral* system changes. If an internal change alters the
  **structure** of a template-owned file (a new field in `brand_voice.py`, a new
  function `leads/page.tsx` depends on), reconcile that file by hand — the sync
  deliberately won't clobber your generic version.
- New hard-coded IDs/secrets you introduce internally should be added to the
  `IDS` / `ID_PATTERNS` / `LEAK` lists in `scripts/_scrub_template.py` so the scrub
  and leak-check know about them.

## CI gate (optional but recommended)

Block any push that would leak brand/secret content:

```bash
python scripts/_scrub_template.py --check   # exit 1 if residue found
```

Wire that into a pre-commit hook or a CI job on this repo.
