import { supabase } from "@/lib/supabase";
import { IdeaCard } from "@/components/idea-card";
import { AddIdeaForm } from "@/components/add-idea-form";

export const dynamic = "force-dynamic";

const SOURCE_LABEL: Record<string, string> = {
  slack: "Slack DM",
  manual: "You (dashboard)",
  auto_trend: "Trending",
  auto_skool: "Skool",
  auto_brand: "Brand-voice fallback",
};

export default async function IdeasPage() {
  const { data: pending } = await supabase
    .from("content_ideas")
    .select("*")
    .eq("status", "pending")
    .order("priority", { ascending: false })
    .order("created_at", { ascending: false });

  const { data: recent } = await supabase
    .from("content_ideas")
    .select("*")
    .in("status", ["used", "dismissed"])
    .order("updated_at", { ascending: false })
    .limit(12);

  // For the used ideas, pull the drafts each one produced so you can see
  // exactly what "Use Now" created (this is the trend → content linkage).
  const usedIds = (recent ?? []).filter((i) => i.status === "used").map((i) => i.id);
  let draftsByIdea: Record<string, any[]> = {};
  if (usedIds.length) {
    const { data: linked } = await supabase
      .from("drafts")
      .select("id, platform, format, status, metadata")
      .in("metadata->>idea_id", usedIds);
    (linked ?? []).forEach((d: any) => {
      const iid = d.metadata?.idea_id;
      if (iid) (draftsByIdea[iid] ??= []).push(d);
    });
  }

  const all = pending ?? [];
  // Ideas you hit "Use Now" on get flagged with metadata.use_now_requested_at.
  // They're generating drafts in the background (drains every 2 min) — move
  // them out of the active queue into a "Generating" section so the click
  // gives immediate feedback instead of the idea appearing to sit there.
  const generating = all.filter(
    (i) => (i.metadata as any)?.use_now_requested_at,
  );
  const list = all.filter((i) => !(i.metadata as any)?.use_now_requested_at);
  const counts = {
    total: list.length,
    slack: list.filter((i) => i.source === "slack").length,
    trend: list.filter((i) => i.source === "auto_trend").length,
    fallback: list.filter((i) => i.source === "auto_brand").length,
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-2 text-center">
        <Stat label="Queued" value={counts.total} />
        <Stat label="From Slack" value={counts.slack} />
        <Stat label="Trends" value={counts.trend} />
        <Stat label="Fallback" value={counts.fallback} />
      </div>

      <AddIdeaForm />

      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-2">Pending queue</h2>
        {list.length === 0 ? (
          <p className="text-sm text-gray-500 italic">
            No pending ideas. Drop something in your Slack DMs to the bot — it'll
            land here within 2 minutes. The system also pulls trends every morning
            and generates brand-voice ideas if the queue gets thin.
          </p>
        ) : (
          <div className="space-y-2">
            {list.map((idea) => (
              <IdeaCard key={idea.id} idea={idea} sourceLabel={SOURCE_LABEL[idea.source] ?? idea.source} />
            ))}
          </div>
        )}
      </div>

      {generating.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-700 mb-2 mt-6">
            ⚙️ Generating posts ({generating.length})
          </h2>
          <p className="text-xs text-gray-500 mb-2">
            You hit Use Now on these. They're generating a LinkedIn post,
            LinkedIn article, Substack, Medium, and Newsletter draft each —
            check the Drafts tab in ~2 minutes.
          </p>
          <div className="space-y-1">
            {generating.map((idea) => (
              <div key={idea.id} className="text-xs border-l-2 border-amber-300 bg-amber-50 pl-2 py-1 rounded-r">
                <span className="font-medium text-amber-700">generating…</span>{" "}
                <span className="text-gray-700">{idea.content.slice(0, 110)}</span>
                {idea.content.length > 110 ? "…" : ""}
              </div>
            ))}
          </div>
        </div>
      )}

      {recent && recent.some((i) => i.status === "used") && (
        <div>
          <h2 className="text-sm font-semibold text-gray-700 mb-2 mt-6">
            ✅ Used — trends turned into content
          </h2>
          <p className="text-xs text-gray-500 mb-2">
            What “Use Now” created. Each badge is a draft — open the Drafts tab
            to approve them.
          </p>
          <div className="space-y-2">
            {recent
              .filter((i) => i.status === "used")
              .map((idea) => (
                <UsedIdeaRow
                  key={idea.id}
                  idea={idea}
                  drafts={draftsByIdea[idea.id] ?? []}
                  sourceLabel={SOURCE_LABEL[idea.source] ?? idea.source}
                />
              ))}
          </div>
        </div>
      )}

      {recent && recent.some((i) => i.status === "dismissed") && (
        <div>
          <h2 className="text-sm font-semibold text-gray-700 mb-2 mt-6">Recently dismissed</h2>
          <div className="space-y-1">
            {recent
              .filter((i) => i.status === "dismissed")
              .map((idea) => (
                <div key={idea.id} className="text-xs text-gray-500 border-l-2 border-gray-200 pl-2 py-1">
                  {SOURCE_LABEL[idea.source] ?? idea.source} — {idea.content.slice(0, 120)}
                  {idea.content.length > 120 ? "…" : ""}
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

const PLATFORM_BADGE: Record<string, string> = {
  linkedin: "bg-blue-100 text-blue-800",
  substack: "bg-orange-100 text-orange-800",
  medium: "bg-gray-200 text-gray-800",
  newsletter: "bg-purple-100 text-purple-800",
};
const STATUS_MARK: Record<string, string> = {
  published: "✓",
  approved: "→",
  edited: "→",
  pending: "•",
  rejected: "✕",
  failed: "!",
};

function UsedIdeaRow({
  idea,
  drafts,
  sourceLabel,
}: {
  idea: any;
  drafts: any[];
  sourceLabel: string;
}) {
  return (
    <div className="border-l-2 border-green-300 bg-green-50/40 pl-2 py-1.5 rounded-r">
      <div className="text-xs text-gray-700">
        <span className="text-[10px] uppercase tracking-wide text-gray-500">{sourceLabel}</span>{" "}
        {idea.content.slice(0, 130)}
        {idea.content.length > 130 ? "…" : ""}
      </div>
      {drafts.length > 0 ? (
        <div className="flex flex-wrap gap-1 mt-1">
          {drafts.map((d) => (
            <span
              key={d.id}
              className={`badge text-[10px] ${PLATFORM_BADGE[d.platform] ?? "bg-gray-100"}`}
              title={`${d.platform} ${d.format ?? ""} — ${d.status}`}
            >
              {STATUS_MARK[d.status] ?? "•"} {d.platform}
              {d.format === "article" ? " article" : ""}
            </span>
          ))}
        </div>
      ) : (
        <div className="text-[10px] text-gray-400 mt-0.5">drafts generating…</div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-gray-200 p-2">
      <div className="text-xl font-bold">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-gray-500">{label}</div>
    </div>
  );
}
