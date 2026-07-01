# The Daily Routine (~1 hour)

Once you're set up, this is how you run the flywheel. The system does the
production; you do the judgment — approve, engage, and pick who to pursue.

Everything happens on your dashboard plus your Airtable base. The morning brief
(Slack DM, if you connected it) tells you exactly what's waiting.

---

## The mental model

**Dashboard** (approve + engage + drop posts) → **Airtable CRM** (work the leads)
→ **SmartLead** (auto-sends + follows up). One direction, every day.

Nothing auto-spends and nothing auto-sends to a stranger — *you* decide who gets
enriched and who gets emailed.

---

## Block 1 — Approve the content (~10 min)
1. Open the dashboard → **Drafts**. The system has queued posts in your voice
   (from your last recording or your idea queue), each with a visual.
2. Bulk-approve the good ones; open any you want to tweak, edit a line, approve.
   Your edits are logged so the voice gets sharper over time.
3. Approved posts publish themselves at the right times — LinkedIn + newsletter via
   API, Substack/Medium via the browser-runner. You don't touch the publishing.

## Block 2 — Engage on LinkedIn (~20–30 min)
1. Dashboard → **Comments**. ~10 posts are queued, each with a comment drafted in
   your voice, found safely (no automation on your account).
2. For each: **Open & comment** → the post opens on LinkedIn → paste the suggested
   comment, tweak a word so it's unmistakably you, post it → mark **✓ Commented**
   (or **Skip**).
3. While you engage, **note posts with lots of good commenters** — your ICP. Those
   are your lead sources for the next block.

## Block 3 — Feed the lead funnel (~5 min)
1. For each good post you found: copy its URL → dashboard **Leads** tab → paste →
   **Scrape**. (Or use the browser plugin's "Scrape this post" right on LinkedIn.)
2. The system pulls that post's commenters into your **Airtable CRM** and dedupes
   them. Watch the job go *running → done*.

## Block 4 — Work the leads in Airtable (~15–20 min)
1. Open your base (the **Open in Airtable** link on the Leads tab). New **Contacts**
   are the commenters, with what they said.
2. For the promising ones:
   - Set **Voice** + **Offer**.
   - Check **Enrich** → ~3 min later: company + a verified work email fill in (plus a
     linked Company row).
   - Check **Create email** → a personalized cold email drafts — it opens on the
     substance of what they talked about, then makes your offer. Not right? Add
     **Feedback** + check **Rerun**.
   - Happy with it + there's an email? Check **Push to campaign** → it drops into
     your SmartLead campaign. Status flips to `in campaign`.

## Block 5 — Sending (automated — you just monitor)
SmartLead sends the offer + follow-ups over ~2 weeks, weekdays only, and **stops the
instant someone replies**. Replies land in your inbox — take the conversation from there.

---

## Weekly
- Record (or write) your source material — one good session feeds a week of content.
- Skim the **Ideas** tab; **Use Now** on anything you want turned into drafts immediately.
- Glance at the Friday digest (what published, engagement, new leads).

## Optional block — Work your podcast leads (~10 min)
If you connected SpeakerAgent.ai:

1. Open the dashboard → **SpeakerAgent**.
2. Review new podcast leads and saved leads.
3. Hit **Generate pitch** on the ones worth working so SpeakerAgent enriches the host and drafts the outreach.
4. Send from your own inbox.
5. Mark status as you move a lead from `New` to `Contacted`, `Replied`, or `Booked`.

## Guardrails (the things that cost money or reach real people)
- **Only Enrich leads worth working** — enrichment burns credits; don't bulk-enrich.
- **Always read a drafted email before Push** — it's going to a real person.
- **No verified email → don't push.**
- **SpeakerAgent status is safe; email send is still manual.**
- Keep comments human — adapt the suggestion, don't paste it robotically.
- Quality over volume: a handful of strong leads a day beats a dump.

> Want to add a channel (newsletter, Substack, the lead engine) later, or change your
> voice/offer? Re-open the repo in Claude Code and say what you want — the assistant
> picks up where setup left off.
