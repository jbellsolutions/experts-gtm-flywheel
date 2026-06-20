type Props = {
  lastIdeaAt: string | null;
  lastDraftCreated: string | null;
  lastDraftPublished: string | null;
};

const ROWS = [
  {
    name: "Slack idea poller",
    cadence: "every 2 min",
    valueKey: "ideaPoll" as const,
    hint: "Reads your DMs to the bot and queues ideas at priority 90",
  },
  {
    name: "Use Now drain",
    cadence: "every 2 min",
    valueKey: "lastDraft" as const,
    hint: "Picks up ideas flagged via the 'Use Now' button and generates 1 LinkedIn + 1 Substack + 1 Medium draft each",
  },
  {
    name: "Publisher",
    cadence: "7am / 12pm / 3pm / 5pm ET",
    valueKey: "lastPublished" as const,
    hint: "Pushes any approved drafts whose scheduled_for has passed",
  },
  {
    name: "Repurposer (transcripts)",
    cadence: "Tue/Thu 22:30 UTC",
    valueKey: "lastDraft" as const,
    hint: "Generates ~22 drafts per YouTube live",
  },
  {
    name: "Repurposer (ideas)",
    cadence: "21 UTC Sun/Mon/Wed/Fri/Sat",
    valueKey: "lastDraft" as const,
    hint: "Off-cycle: turns queued ideas into drafts on non-recording days",
  },
  {
    name: "Trends scraper",
    cadence: "daily 4am ET",
    valueKey: "ideaPoll" as const,
    hint: "Pulls AI/automation posts from Hacker News + Reddit",
  },
  {
    name: "Brand-voice fallback",
    cadence: "every 6h (only if <5 pending ideas)",
    valueKey: "ideaPoll" as const,
    hint: "Generates 8 ideas in your voice when the queue runs thin",
  },
  {
    name: "Stats fetcher",
    cadence: "Friday 1pm ET",
    valueKey: "lastPublished" as const,
    hint: "Snapshots engagement (likes/comments/reposts) for last 30 days of posts",
  },
];

function fmt(ts: string | null | undefined) {
  if (!ts) return "—";
  const d = new Date(ts);
  const ageMs = Date.now() - d.getTime();
  if (ageMs < 60_000) return "just now";
  if (ageMs < 3600_000) return `${Math.round(ageMs / 60_000)}m ago`;
  if (ageMs < 86_400_000) return `${Math.round(ageMs / 3600_000)}h ago`;
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function SystemStatus(props: Props) {
  const values = {
    ideaPoll: props.lastIdeaAt,
    lastDraft: props.lastDraftCreated,
    lastPublished: props.lastDraftPublished,
  };
  return (
    <details className="card !p-4">
      <summary className="cursor-pointer text-sm font-semibold text-gray-700">
        System status — polling & last activity
      </summary>
      <table className="w-full text-xs mt-3">
        <thead>
          <tr className="text-left text-gray-500 border-b border-gray-100">
            <th className="py-1 font-medium">Job</th>
            <th className="py-1 font-medium">Cadence</th>
            <th className="py-1 font-medium text-right">Last</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((r) => (
            <tr key={r.name} className="border-b border-gray-50">
              <td className="py-1.5">
                <div className="text-gray-900">{r.name}</div>
                <div className="text-[10px] text-gray-500">{r.hint}</div>
              </td>
              <td className="py-1.5 text-gray-600">{r.cadence}</td>
              <td className="py-1.5 text-right text-gray-700 tabular-nums">
                {fmt(values[r.valueKey])}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
