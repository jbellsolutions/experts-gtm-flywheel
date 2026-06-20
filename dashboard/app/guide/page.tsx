export const dynamic = "force-static";

export default function GuidePage() {
  return (
    <article className="prose prose-sm max-w-none space-y-6 text-gray-800">
      <Section title="What this is">
        <p>
          Your brand organic content flywheel — a LinkedIn-first authority
          engine. The two YouTube lives you record each week (plus ideas you
          drop into Slack) become a steady weekly stream of LinkedIn posts,
          one Substack issue, one Medium article, and one Kit newsletter
          broadcast — all in your voice, all reviewed by you before they ship.
        </p>
        <p>
          <strong>Your job is small.</strong> Record 2 lives a week. Spend
          ~30-45 min/day reviewing what the system queued. That's it.
        </p>
      </Section>

      <Section title="The two pillars (everything maps to these)">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
            <h4 className="font-semibold text-blue-900">Pillar 1 — Help first</h4>
            <p className="text-blue-900/80 mt-1">
              "Ask me anything, I'll just tell you the answer." Generous,
              approachable. Posts ask real questions ("What's the workflow
              eating your team's time?") and offer real answers in the
              comments. This pillar starts conversations.
            </p>
          </div>
          <div className="rounded-lg border border-purple-200 bg-purple-50 p-4">
            <h4 className="font-semibold text-purple-900">Pillar 2 — The Journey</h4>
            <p className="text-purple-900/80 mt-1">
              Your origin + mission story. Building in
              public. This pillar builds authority that makes businesses trust
              you with real work.
            </p>
          </div>
        </div>
        <p className="mt-3">
          Tuesday lives = Pillar 1 (problem-solving). Thursday lives = Pillar
          2 (journey). The repurposer auto-detects which pillar each draft
          belongs to and tags it.
        </p>
      </Section>

      <Section title="Your daily flow">
        <ol className="list-decimal pl-5 space-y-2">
          <li>
            <strong>5:00 AM ET</strong> — Slack DM lands with today's checklist
            (also shown on the Today tab). It pre-counts queued drafts and
            today's engage list.
          </li>
          <li>
            <strong>~6:15 AM</strong> — Open this dashboard. Work three tabs:
            <ul className="list-disc pl-5 mt-1 space-y-1">
              <li><strong>Drafts</strong> — bulk-approve or open each, edit, approve. Edits are logged so the voice gets sharper over time.</li>
              <li><strong>Comments</strong> — today's 10 LinkedIn posts to comment on. Each comes with an AI-drafted comment in your voice. Click → open → comment.</li>
              <li><strong>Ideas</strong> — anything new in the queue (Slack DMs, trends, LLM-suggested). Boost, dismiss, or hit <strong>Use Now</strong> to immediately generate 1 LinkedIn + 1 Substack + 1 Medium draft from it.</li>
            </ul>
          </li>
          <li>
            <strong>Throughout the day</strong> — LinkedIn and Newsletter (Kit) post themselves at 7am / 12pm / 3pm / 5pm ET. Substack and Medium publish via Browser Use Cloud using their captured profiles.
          </li>
          <li>
            <strong>Tue/Thu evening</strong> — Record the live. Done. Overnight, the system pulls the transcript and generates the week's drafts.
          </li>
          <li>
            <strong>Friday 5pm ET</strong> — Weekly digest in Slack: this week's published count + engagement totals.
          </li>
        </ol>
      </Section>

      <Section title="The 4 platforms (and only these)">
        <table className="text-sm w-full">
          <thead><tr className="border-b text-xs uppercase text-gray-500"><td className="py-1.5">Platform</td><td>Mechanism</td><td>Cadence</td></tr></thead>
          <tbody className="[&>tr>td]:py-1.5 [&>tr>td:first-child]:pr-3 [&>tr>td]:pr-3">
            <tr><td><strong>LinkedIn</strong></td><td>Unipile API (your account)</td><td>~2/day + repurpose</td></tr>
            <tr><td><strong>Substack</strong></td><td>Browser Use Cloud profile</td><td>1/week</td></tr>
            <tr><td><strong>Medium</strong></td><td>Browser Use Cloud profile</td><td>1/week</td></tr>
            <tr><td><strong>Newsletter (Kit)</strong></td><td>Kit v4 broadcast API — fully automated</td><td>1/week (Fri 8am)</td></tr>
          </tbody>
        </table>
        <p className="mt-2">
          Twitter, Facebook, YouTube Shorts, and inbound DM monitoring were all
          removed in the June 2026 cleanup. See <code>MIGRATION.md</code> for the
          history.
        </p>
      </Section>

      <Section title="Idea queue → drafts">
        <p>
          Every Idea you see in the <strong>Ideas</strong> tab can become a set
          of LinkedIn/Substack/Medium drafts. Sources of ideas:
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li><strong>Slack DM to the bot</strong> (priority 90) — text, YouTube link, or any URL. YouTube transcripts auto-pull. Generic URLs auto-fetch via jina.ai.</li>
          <li><strong>Trends scraper</strong> (priority 50) — daily 4am ET pull from Hacker News + Reddit, AI/automation only.</li>
          <li><strong>Brand-voice fallback</strong> (priority 30) — every 6h, if queue &lt; 5, generates voice-aligned ideas from your pillars.</li>
          <li><strong>Manual add</strong> (priority 80) — paste directly in the Ideas tab.</li>
        </ul>
        <p>
          Click <strong>Use Now</strong> on any idea → within 2 min, three new
          drafts (one LinkedIn, one Substack, one Medium) appear in the Drafts
          tab. Otherwise the off-cycle 21:00 UTC cron drains queued ideas
          automatically on non-recording days.
        </p>
      </Section>

      <Section title="Where everything lives">
        <table className="text-sm w-full">
          <tbody className="[&>tr>td]:py-1.5 [&>tr>td:first-child]:pr-3 [&>tr>td:first-child]:font-medium [&>tr>td:first-child]:whitespace-nowrap">
            <tr><td>Dashboard</td><td>Next.js 14 on Railway. The only UI you ever open.</td></tr>
            <tr><td>Worker</td><td>Python cron on Railway. ~16 scheduled jobs.</td></tr>
            <tr><td>Browser-runner</td><td>Python + Browser Use Cloud SDK on Railway. Drives Substack/Medium publishing.</td></tr>
            <tr><td>Redis</td><td>Job queue between worker and browser-runner.</td></tr>
            <tr><td>Supabase</td><td>transcripts, drafts, content_ideas, influencers, daily_checklists, post_metrics, kv_state. Leads live in Airtable.</td></tr>
            <tr><td>Slack DMs</td><td>5am checklist · publish failures · Friday digest. All to your DM.</td></tr>
          </tbody>
        </table>
      </Section>

      <Section title="Cost guardrails">
        <p>
          Per-task model selection lives in <code>repurposer/model_config.py</code>.
          Default split: Sonnet 4.5 for voice-critical (LinkedIn, Substack,
          Medium, newsletter), Haiku 4.5 for short/cheap (suggested comments,
          replies). Runs ~$10/mo on Anthropic for 2 transcripts/week + the
          idea-queue flow.
        </p>
        <p>
          To change the model for any task, edit one line in
          <code>model_config.py</code>, push to GitHub, Railway redeploys
          automatically.
        </p>
      </Section>

      <Section title="When something breaks">
        <ul className="list-disc pl-5 space-y-1">
          <li><strong>Substack/Medium publish fails</strong> — the Browser Use Cloud profile session expired. Open cloud.browser-use.com → profile → re-capture the login. No code changes needed.</li>
          <li><strong>LinkedIn publish fails</strong> — Unipile token rotation or account disconnect. Check the Unipile dashboard.</li>
          <li><strong>Newsletter fails</strong> — Kit account state. Verify the API key still works against api.kit.com/v4/account.</li>
          <li><strong>Slack stops DMing</strong> — bot scopes might have reset. Verify <code>chat:write</code> + <code>im:write</code> on the bot in Slack admin. The hybrid bot/user token wiring also requires <code>SLACK_USER_TOKEN</code> for read calls.</li>
          <li><strong>Voice drifting</strong> — open <code>repurposer/brand_voice.py</code> and add your best recent posts to <code>FEW_SHOT_LINKEDIN</code>. Or wait for the Sunday auto-tune job to do it for you.</li>
        </ul>
      </Section>

      <Section title="The recipe for a great day">
        <ol className="list-decimal pl-5 space-y-1">
          <li>Open the Today tab. Knock out the items.</li>
          <li>Approve drafts. Drop 5 substantive comments on others' LinkedIn posts.</li>
          <li>Record the live (Tue/Thu only). Don't script it. Real, conversational, generous.</li>
          <li>Trust the system to do the rest.</li>
        </ol>
      </Section>
    </article>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-lg font-semibold mb-2 text-gray-900">{title}</h2>
      <div className="text-sm text-gray-700 space-y-2">{children}</div>
    </section>
  );
}
