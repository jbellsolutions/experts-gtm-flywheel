# SmartLead Skills

This repo already knows how to draft offer emails, enrich leads, and push approved
contacts into SmartLead. This document adds the operating skills and guardrails adapted
from the working `single-brain` setup so the public repo exposes the full SmartLead lane
cleanly.

## Pipeline

```text
Lead ingestion
  -> Strategy brief
  -> Research signals
  -> Copy draft
  -> SmartLead campaign draft
  -> Operator review
  -> Send + follow-up
  -> Reply loop
```

The system is designed so nothing sends just because a lead exists. The operator decides
which leads get enriched, which emails get pushed, and when the SmartLead campaign is
started.

## Campaign skills

- Campaign naming follows `<niche>-<offer>-<variant>` so campaigns stay reusable and easy to audit.
- Email 1 is the per-lead draft carried in `{{email_subject}}` and `{{email_body}}`.
- Follow-ups are stored as SmartLead sequence variants, not raw Spintax.
- Campaigns are created in a review-safe state first. Add inboxes and start them only after inspection.
- Lead pushes are idempotent and reuse the existing campaign rather than cloning workflow state.

## Voice and safety rules

- No URLs in emails 1 through 3.
- Keep the first sequence compact: 125 / 150 / 125 words is the default envelope.
- Use a reply-based CTA, not a booking-link CTA.
- Keep threading intact. Follow-ups should stay inside the same subject line unless you intentionally change the campaign strategy.
- Stop on reply. SmartLead should never keep advancing a prospect once they answer.
- Keep the tone operator-to-operator, not agency-pitchy.

## Validation gates

Before a draft should be pushed:

- Slop check: reject generic AI phrasing.
- Sales check: reject fake urgency, fake timeframes, and hype language.
- URL check: reject links in the early sequence.
- Threading check: make sure follow-ups preserve the conversation structure.

## Daily operating rhythm

1. Review campaign stats.
2. Review unread inbox replies.
3. Work Airtable contacts that are actually worth enriching.
4. Generate or rerun email drafts only after the lead is qualified.
5. Push approved leads to SmartLead.
6. Triage human replies from your inbox or reply queue.

## Reply handling

- Auto-handle: out-of-office, unsubscribe, and obvious spam.
- Human review: positive replies, objections, questions, and any ambiguous response.
- If you add automations, keep the final send action human-approved unless the class is trivial and safe.

## Key commands

```bash
export SMARTLEAD_API_KEY=<your-key>

python scripts/smartlead_setup.py --create --name "Brand Outreach"
python scripts/smartlead_setup.py --campaign <campaign-id>
```

```bash
smartlead campaigns list --format json
smartlead inbox unread --format json
smartlead leads list --campaign-id <ID>
smartlead leads export --campaign-id <ID> --output leads.csv
smartlead analytics overview --from YYYY-MM-DD --to YYYY-MM-DD
```

The repo does not require the external SmartLead CLI to function, but these commands are
useful if you already operate SmartLead from a shell or another agent environment.
