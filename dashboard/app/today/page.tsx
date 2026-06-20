import { supabase } from "@/lib/supabase";
import { ChecklistItem } from "@/components/checklist-item";
import { SystemStatus } from "@/components/system-status";

export const dynamic = "force-dynamic";

function todayET(): string {
  const now = new Date();
  const et = new Date(now.getTime() - 4 * 60 * 60 * 1000);
  return et.toISOString().slice(0, 10);
}

const SCOPE_HEADERS: Record<string, { label: string; sub: string }> = {
  morning:   { label: "🌅 Morning",   sub: "15-20 min · triage & approve" },
  engage:    { label: "🤝 Engage Out", sub: "30-45 min · grow the audience" },
  midday:    { label: "🍽️ Midday",     sub: "10 min · sweep" },
  afternoon: { label: "🕒 Afternoon",  sub: "" },
  evening:   { label: "🌙 Evening",    sub: "10 min · wrap" },
  friday:    { label: "📊 Friday Weekly Review", sub: "30 min" },
};

const SCOPE_ORDER = ["morning", "engage", "midday", "afternoon", "evening", "friday"];

const PLATFORM_BADGE: Record<string, string> = {
  linkedin:   "bg-blue-100 text-blue-800",
  substack:   "bg-orange-100 text-orange-800",
  medium:     "bg-gray-100 text-gray-800",
  newsletter: "bg-purple-100 text-purple-800",
};

export default async function TodayPage() {
  const date = todayET();
  const [{ data }, ideaLatestRes, draftLatestRes, publishedLatestRes] =
    await Promise.all([
      supabase.from("daily_checklists").select("*").eq("date", date).single(),
      supabase
        .from("content_ideas")
        .select("created_at")
        .order("created_at", { ascending: false })
        .limit(1),
      supabase
        .from("drafts")
        .select("created_at")
        .order("created_at", { ascending: false })
        .limit(1),
      supabase
        .from("drafts")
        .select("published_at")
        .eq("status", "published")
        .order("published_at", { ascending: false })
        .limit(1),
    ]);
  const lastIdeaAt = ideaLatestRes.data?.[0]?.created_at ?? null;
  const lastDraftCreated = draftLatestRes.data?.[0]?.created_at ?? null;
  const lastDraftPublished = publishedLatestRes.data?.[0]?.published_at ?? null;

  if (!data) {
    return (
      <div className="card text-center text-gray-500 py-8">
        <p className="text-sm">No checklist generated for today yet.</p>
        <p className="text-xs mt-2">
          The 5am ET cron generates it. If you're seeing this after 5am, check the worker logs in Railway.
        </p>
      </div>
    );
  }

  const items = (data.items as any[]) ?? [];
  const summary = data.summary ?? "";
  const kpis = (data.kpis as any) ?? {};
  const context = (data.context as any) ?? {};

  const grouped: Record<string, any[]> = {};
  for (const item of items) {
    const scope = item.scope ?? "other";
    (grouped[scope] ??= []).push(item);
  }

  const done = items.filter((i) => i.completed).length;
  const total = items.length;

  return (
    <div className="space-y-3">
      {/* ── Header card ───────────────────────────────────────────── */}
      <div className="card !p-4">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold">Today</h2>
          <span className="text-sm text-gray-500">{done}/{total} done</span>
        </div>
        {summary && <p className="text-sm text-gray-600">{summary}</p>}
        <div className="mt-3 h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-ok transition-all"
            style={{ width: total > 0 ? `${(done / total) * 100}%` : "0%" }}
          />
        </div>
      </div>

      {/* ── KPI scoreboard ─────────────────────────────────────────── */}
      <div className="card !p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Week so far</h3>
        <ul className="space-y-2">
          {[
            "linkedin_posts_published",
            "substack_posts_published",
            "medium_articles_published",
            "newsletter_sent",
            "linkedin_comments_given",
            "lives_recorded",
          ].map((k) => {
            const kpi = kpis[k];
            if (!kpi) return null;
            return (
              <li key={k} className="text-sm">
                <div className="flex justify-between gap-2 mb-1">
                  <span className="text-gray-700 truncate">{kpi.label}</span>
                  <span className="text-gray-500 shrink-0 tabular-nums">
                    {kpi.actual}/{kpi.target}
                  </span>
                </div>
                <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all ${
                      kpi.pct >= 100 ? "bg-ok" : kpi.pct >= 50 ? "bg-accent" : "bg-warn"
                    }`}
                    style={{ width: `${kpi.pct}%` }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      </div>

      {/* ── System status (collapsible) ────────────────────────────── */}
      <SystemStatus
        lastIdeaAt={lastIdeaAt}
        lastDraftCreated={lastDraftCreated}
        lastDraftPublished={lastDraftPublished}
      />

      {/* ── Engage list summary ────────────────────────────────────── */}
      {context.li_engage?.length ? (
        <div className="card !p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-700">Today's engagement targets</h3>
            <a href="/comments" className="text-xs text-accent hover:underline">All →</a>
          </div>
          <div className="rounded border border-gray-200 p-2 text-center">
            <div className="text-xl font-bold text-blue-700">{context.li_engage?.length ?? 0}</div>
            <div className="text-[10px] uppercase tracking-wide text-gray-500">LinkedIn posts to comment on</div>
          </div>
        </div>
      ) : null}

      {/* ── Specifics: drafts due today ─────────────────────────────── */}
      {context.drafts_today?.length > 0 && (
        <div className="card !p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">What's on deck</h3>

          <details open>
            <summary className="text-xs font-medium text-gray-500 cursor-pointer">
              Drafts due today ({context.drafts_today.length})
            </summary>
            <ul className="mt-2 space-y-1">
              {context.drafts_today.map((d: any) => (
                <li key={d.id} className="flex items-start gap-2 text-xs">
                  <span className={`badge shrink-0 ${PLATFORM_BADGE[d.platform] ?? "bg-gray-100"}`}>
                    {d.platform} · P{d.pillar}
                  </span>
                  <span className="text-gray-700 line-clamp-1">{d.body_preview}</span>
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}

      {/* ── Checklist by time block ────────────────────────────────── */}
      {SCOPE_ORDER.map((scope) => {
        const list = grouped[scope] ?? [];
        if (list.length === 0) return null;
        const header = SCOPE_HEADERS[scope] ?? { label: scope, sub: "" };
        return (
          <div key={scope} className="card">
            <div className="mb-3">
              <h3 className="text-sm font-semibold text-gray-700">{header.label}</h3>
              {header.sub && <p className="text-xs text-gray-500">{header.sub}</p>}
            </div>
            <ul className="space-y-3">
              {list.map((item) => (
                <ChecklistItem key={item.id} date={date} item={item} />
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
