import { supabase } from "@/lib/supabase";
import { DraftCard } from "@/components/draft-card";
import { ApproveAllBar } from "@/components/approve-all-bar";
import { PublishedCard } from "@/components/published-card";

export const dynamic = "force-dynamic";

export default async function DraftsPage({
  searchParams,
}: {
  searchParams?: { col?: string };
}) {
  const col = (searchParams?.col ?? "pending") as
    | "pending"
    | "approved"
    | "published"
    | "failed";

  const now = new Date();
  const thirtyAgo = new Date(now);
  thirtyAgo.setDate(thirtyAgo.getDate() - 30);

  const [pendingRes, approvedRes, publishedRes, failedRes, metricsRes, activityRes] = await Promise.all([
    // Pending = ALL pending, regardless of slot time. Past-due drafts get
    // an "overdue" badge in the card so they're visible, not hidden.
    supabase
      .from("drafts")
      .select("*")
      .eq("status", "pending")
      .order("scheduled_for", { ascending: true, nullsFirst: false }),
    supabase
      .from("drafts")
      .select("*")
      .in("status", ["approved", "edited"])
      .order("scheduled_for"),
    supabase
      .from("drafts")
      .select("*")
      .eq("status", "published")
      .gte("published_at", thirtyAgo.toISOString())
      .order("published_at", { ascending: false }),
    supabase
      .from("drafts")
      .select("*")
      .eq("status", "failed")
      .order("updated_at", { ascending: false }),
    supabase
      .from("post_metrics_latest")
      .select("draft_id, impressions, likes, comments, reposts, engagement, snapshot_at"),
    // Last 7 days of activity for the per-day strip
    supabase
      .from("drafts")
      .select("status, created_at, scheduled_for, published_at")
      .or(
        `created_at.gte.${new Date(now.getTime() - 7 * 86400000).toISOString()},` +
        `published_at.gte.${new Date(now.getTime() - 7 * 86400000).toISOString()}`,
      ),
  ]);

  const pending = pendingRes.data ?? [];
  const approved = approvedRes.data ?? [];
  const published = publishedRes.data ?? [];
  const failed = failedRes.data ?? [];
  const metricsByDraft: Record<string, any> = {};
  (metricsRes.data ?? []).forEach((m: any) => (metricsByDraft[m.draft_id] = m));
  const overdueCount = pending.filter(
    (d) => d.scheduled_for && new Date(d.scheduled_for) < now,
  ).length;

  const totalEngagement = published.reduce(
    (sum, d) => sum + (metricsByDraft[d.id]?.engagement ?? 0),
    0,
  );

  const activity = activityRes.data ?? [];
  const days: { date: string; created: number; approved: number; published: number }[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    days.push({ date: key, created: 0, approved: 0, published: 0 });
  }
  for (const r of activity) {
    const created = (r.created_at ?? "").slice(0, 10);
    const pub = (r.published_at ?? "").slice(0, 10);
    const day = days.find((x) => x.date === created);
    if (day) day.created += 1;
    if (r.status === "approved" || r.status === "edited") {
      const dApp = days.find((x) => x.date === created);
      if (dApp) dApp.approved += 1;
    }
    if (pub) {
      const dPub = days.find((x) => x.date === pub);
      if (dPub) dPub.published += 1;
    }
  }

  const list =
    col === "pending" ? pending
    : col === "approved" ? approved
    : col === "failed" ? failed
    : published;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-4 gap-2 mb-2">
        <PipelineTab
          href="/drafts?col=pending"
          active={col === "pending"}
          label="Pending"
          value={pending.length}
          sub={overdueCount > 0 ? `${overdueCount} overdue` : "queued"}
        />
        <PipelineTab
          href="/drafts?col=approved"
          active={col === "approved"}
          label="Approved"
          value={approved.length}
          sub="awaiting publish"
        />
        <PipelineTab
          href="/drafts?col=published"
          active={col === "published"}
          label="Published"
          value={published.length}
          sub={`${totalEngagement} ❤︎ · 30d`}
        />
        <PipelineTab
          href="/drafts?col=failed"
          active={col === "failed"}
          label="Failed"
          value={failed.length}
          sub={failed.length === 0 ? "none" : "click to retry"}
          danger={failed.length > 0}
        />
      </div>

      <ActivityStrip days={days} />

      {col === "pending" && (
        <ApproveAllBar ids={list.map((d) => d.id)} count={list.length} />
      )}

      {list.length === 0 && (
        <div className="card text-center text-gray-500 py-8">
          {col === "pending"
            ? "Nothing queued. The next live's repurpose job will fill this."
            : col === "approved"
            ? "Nothing waiting. Approve some pending drafts and they'll land here."
            : col === "failed"
            ? "No failed drafts — publishing is healthy. ✓"
            : "Nothing published in the last 30 days yet."}
        </div>
      )}

      {col === "published"
        ? list.map((d) => (
            <PublishedCard key={d.id} draft={d} metrics={metricsByDraft[d.id]} />
          ))
        : list.map((d) => <DraftCard key={d.id} draft={d} />)}
    </div>
  );
}

function ActivityStrip({
  days,
}: {
  days: { date: string; created: number; approved: number; published: number }[];
}) {
  const dayName = (iso: string) => {
    const d = new Date(iso + "T12:00:00Z");
    return d.toLocaleDateString([], { weekday: "short" });
  };
  return (
    <div className="card !p-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-gray-700">Activity (last 7 days)</h3>
        <div className="text-[10px] text-gray-500 flex gap-2">
          <span><span className="inline-block w-2 h-2 rounded-sm bg-gray-400 mr-1" />created</span>
          <span><span className="inline-block w-2 h-2 rounded-sm bg-amber-400 mr-1" />approved</span>
          <span><span className="inline-block w-2 h-2 rounded-sm bg-emerald-500 mr-1" />published</span>
        </div>
      </div>
      <div className="grid grid-cols-7 gap-1">
        {days.map((d) => (
          <div key={d.date} className="text-center">
            <div className="text-[10px] text-gray-500">{dayName(d.date)}</div>
            <div className="text-[10px] font-mono text-gray-600">
              <span className="text-gray-700">{d.created}</span>
              {" / "}
              <span className="text-amber-600">{d.approved}</span>
              {" / "}
              <span className="text-emerald-600">{d.published}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PipelineTab({
  href,
  active,
  label,
  value,
  sub,
  danger,
}: {
  href: string;
  active: boolean;
  label: string;
  value: number;
  sub: string;
  danger?: boolean;
}) {
  return (
    <a
      href={href}
      className={`card !p-3 block text-center transition ${
        active ? "ring-2 ring-accent" : "hover:bg-gray-50"
      } ${danger ? "border-red-300 bg-red-50" : ""}`}
    >
      <div className={`text-2xl font-semibold ${danger ? "text-red-700" : ""}`}>{value}</div>
      <div className="text-xs font-medium text-gray-700">{label}</div>
      <div className="text-[10px] text-gray-500 mt-0.5">{sub}</div>
    </a>
  );
}
