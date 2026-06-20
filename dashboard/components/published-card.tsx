import { fmtTime } from "@/lib/utils";

type Metrics = {
  impressions: number | null;
  likes: number | null;
  comments: number | null;
  reposts: number | null;
  engagement: number | null;
  snapshot_at: string | null;
};

export function PublishedCard({
  draft,
  metrics,
}: {
  draft: any;
  metrics?: Metrics;
}) {
  const pillarBadge =
    draft.pillar === "1"
      ? "bg-blue-100 text-blue-800"
      : draft.pillar === "2"
      ? "bg-purple-100 text-purple-800"
      : "bg-gray-100 text-gray-800";

  return (
    <div className="card">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="badge bg-gray-900 text-white">{draft.platform}</span>
          <span className={`badge ${pillarBadge}`}>P{draft.pillar}</span>
          <span className="text-xs text-gray-500 truncate">{draft.format}</span>
        </div>
        <span className="text-xs text-gray-500 shrink-0">
          {fmtTime(draft.published_at ?? draft.scheduled_for)}
        </span>
      </div>

      <p className="text-sm text-gray-700 line-clamp-3 mb-2">{draft.body}</p>

      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-3 text-xs text-gray-700">
          {metrics ? (
            <>
              {metrics.impressions != null && (
                <Stat icon="👁" label="impressions" value={metrics.impressions} />
              )}
              <Stat icon="❤︎" label="likes" value={metrics.likes ?? 0} />
              <Stat icon="💬" label="comments" value={metrics.comments ?? 0} />
              {metrics.reposts != null && (
                <Stat icon="↻" label="reposts" value={metrics.reposts} />
              )}
              <span className="text-[10px] text-gray-400 ml-1">
                as of {metrics.snapshot_at ? new Date(metrics.snapshot_at).toLocaleDateString() : "—"}
              </span>
            </>
          ) : (
            <span className="text-xs text-gray-400 italic">
              no stats yet — Friday refresh pulls these
            </span>
          )}
        </div>
        {draft.publish_url && (
          <a
            href={draft.publish_url}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-accent hover:underline"
          >
            view post ↗
          </a>
        )}
      </div>
    </div>
  );
}

function Stat({ icon, label, value }: { icon: string; label: string; value: number }) {
  return (
    <span title={label} className="inline-flex items-center gap-1">
      <span aria-hidden>{icon}</span>
      <span className="font-medium">{fmtNum(value)}</span>
    </span>
  );
}

function fmtNum(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "k";
  return String(n);
}
